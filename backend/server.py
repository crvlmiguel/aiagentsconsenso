"""Consenso Plus — AI Business Operating System (multi-tenant SaaS backend)."""
import os
import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from models import (
    Tenant, User, RegisterInput, LoginInput, AuthResponse,
    Agent, AgentInput,
    DataSource, DataSourceURLInput, DataSourceTextInput,
    Conversation, Message, InboundMessage, SendMessageInput,
    Lead, LeadInput,
    Ticket, TicketInput,
    TeamInvite,
    now_iso, new_id,
)
from auth import hash_password, verify_password, create_token, current_user
from ai.intent import classify_intent
from ai.structure import structure_message
from ai.orchestrator import decide_actions, generate_response
from ai.tools import execute_actions
from ai.retrieval import scrape_url, build_chunks, retrieve
from ai.router import test_connection as llm_test_connection, LLMConfigMissing, LLMProviderError
from email_service import send_email, render_lead_email
from ws_manager import manager as ws_manager
from webhooks import build_router as build_webhooks_router

from langdetect import detect as detect_lang, DetectorFactory
DetectorFactory.seed = 0

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Consenso Plus API")
api = APIRouter(prefix="/api")

logger = logging.getLogger("consenso")


def _detect(text: str, default: str = "pt") -> str:
    try:
        code = detect_lang(text)
        return code[:2] if code else default
    except Exception:
        return default


async def _notify_new_lead(tenant_id: str, lead_id: str, agent: dict) -> None:
    """Send an email notification using the AGENT's own SMTP config (agent-centric)."""
    email_cfg = (agent or {}).get("email") or {}
    if not email_cfg.get("enabled"):
        return
    if not email_cfg.get("host") or not email_cfg.get("from_email"):
        return
    to = email_cfg.get("notify_email") or agent.get("notify_email") or email_cfg.get("from_email")
    if not to:
        return
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        return
    html = render_lead_email(lead)
    subject = f"Novo lead · {lead.get('name', '')}"
    result = send_email(email_cfg, to, subject, html)
    logger.info(f"Lead email notify {lead_id} → {to}: {result}")
    await db.leads.update_one({"id": lead_id}, {"$set": {"email_notified": bool(result.get("ok"))}})


# ======================== AUTH ========================
@api.post("/auth/register", response_model=AuthResponse)
async def register(inp: RegisterInput):
    existing = await db.users.find_one({"email": inp.email}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Email já registado")

    tenant_id = new_id()
    slug = inp.company_name.lower().replace(" ", "-")[:40]
    tenant_doc = {
        "id": tenant_id, "name": inp.company_name, "slug": slug,
        "plan": "pro", "default_language": "pt", "created_at": now_iso(),
    }
    await db.tenants.insert_one(tenant_doc.copy())

    user_id = new_id()
    user_doc = {
        "id": user_id, "tenant_id": tenant_id, "email": inp.email,
        "name": inp.name, "role": "owner",
        "password_hash": hash_password(inp.password),
        "created_at": now_iso(),
    }
    await db.users.insert_one(user_doc.copy())

    await db.agents.insert_one({
        "id": new_id(), "tenant_id": tenant_id,
        "name": "Assistente Principal", "tone": "profissional e simpático",
        "goal": "Ajudar clientes e qualificar leads",
        "system_prompt": f"És o assistente AI da {inp.company_name}. Sê útil, conciso e preciso. Responde sempre em Português Europeu (pt-PT).",
        "rules": "", "model_provider": "auto", "model_name": "gpt-5.1",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
            {"key": "send_email", "enabled": False},
            {"key": "webhook", "enabled": False},
        ],
        "knowledge": "", "data_source_ids": [], "default_language": "pt",
        "notify_email": "",
        "channels": {
            "webchat": {"enabled": True},
            "whatsapp": {"enabled": False, "access_token": "", "phone_number_id": ""},
            "telegram": {"enabled": False, "bot_token": ""},
        },
        "email": {"enabled": False, "host": "", "port": 587, "secure": "tls",
                  "username": "", "password": "", "from_email": "", "notify_email": ""},
        "active": True, "created_at": now_iso(),
    })

    token = create_token(user_id, tenant_id, "owner")
    return AuthResponse(
        token=token,
        user=User(**{k: v for k, v in user_doc.items() if k != "password_hash"}),
        tenant=Tenant(**tenant_doc),
    )


@api.post("/auth/login", response_model=AuthResponse)
async def login(inp: LoginInput):
    user = await db.users.find_one({"email": inp.email}, {"_id": 0})
    if not user or not verify_password(inp.password, user.get("password_hash", "")):
        raise HTTPException(401, "Credenciais inválidas")
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0})
    token = create_token(user["id"], user["tenant_id"], user.get("role", "owner"))
    user_clean = {k: v for k, v in user.items() if k != "password_hash"}
    return AuthResponse(token=token, user=User(**user_clean), tenant=Tenant(**tenant))


@api.get("/auth/me")
async def me(claims=Depends(current_user)):
    user = await db.users.find_one({"id": claims["sub"]}, {"_id": 0, "password_hash": 0})
    tenant = await db.tenants.find_one({"id": claims["tenant_id"]}, {"_id": 0})
    if not user or not tenant:
        raise HTTPException(404, "Utilizador/tenant não encontrado")
    return {"user": user, "tenant": tenant}


def _agent_is_configured(agent: dict) -> tuple[bool, str]:
    """Validate an agent can run. Returns (ok, error_message_pt)."""
    prov = (agent.get("api_provider") or "emergent").lower()
    if prov == "emergent":
        if not os.environ.get("EMERGENT_LLM_KEY"):
            return False, "API da IA não configurada ou inválida. Configure a Chave Universal Emergent ou uma chave própria no agente."
        return True, ""
    if not (agent.get("api_key") or "").strip():
        return False, "API da IA não configurada ou inválida. Por favor configure a API da IA para ativar o agente."
    if prov not in {"openai", "anthropic", "gemini"}:
        return False, "API da IA não configurada ou inválida. Provider não suportado."
    return True, ""


@api.post("/agents/{agent_id}/test-connection")
async def agent_test_connection(agent_id: str, claims=Depends(current_user)):
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    ok, err = _agent_is_configured(agent)
    if not ok:
        return {"ok": False, "error": err, "code": "config_missing"}
    return await llm_test_connection(agent.get("api_provider", "emergent"), agent.get("api_key", ""), agent.get("model_name"))


@api.post("/test-connection")
async def test_connection_inline(body: dict, claims=Depends(current_user)):
    """Test a connection WITHOUT saving the agent (useful for config panel)."""
    prov = body.get("api_provider", "emergent")
    key = body.get("api_key", "")
    model = body.get("model_name")
    return await llm_test_connection(prov, key, model)


# ======================== DASHBOARD ========================
@api.get("/dashboard/stats")
async def dashboard_stats(claims=Depends(current_user)):
    t = claims["tenant_id"]
    convos = await db.conversations.count_documents({"tenant_id": t})
    open_convos = await db.conversations.count_documents({"tenant_id": t, "status": {"$in": ["ai", "human", "open"]}})
    leads = await db.leads.count_documents({"tenant_id": t})
    tickets_open = await db.tickets.count_documents({"tenant_id": t, "status": {"$in": ["open", "in_progress"]}})
    messages = await db.messages.count_documents({"tenant_id": t})

    pipeline = [{"$match": {"tenant_id": t}}, {"$group": {"_id": "$channel", "count": {"$sum": 1}}}]
    by_channel = [{"channel": d["_id"], "count": d["count"]} async for d in db.conversations.aggregate(pipeline)]

    pipeline2 = [{"$match": {"tenant_id": t}}, {"$group": {"_id": "$stage", "count": {"$sum": 1}}}]
    by_stage = [{"stage": d["_id"], "count": d["count"]} async for d in db.leads.aggregate(pipeline2)]

    return {
        "conversations": convos, "open_conversations": open_convos,
        "leads": leads, "open_tickets": tickets_open,
        "messages": messages, "by_channel": by_channel, "by_stage": by_stage,
    }


# ======================== AGENTS ========================
@api.get("/agents")
async def list_agents(claims=Depends(current_user)):
    return await db.agents.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).to_list(200)


@api.post("/agents")
async def create_agent(inp: AgentInput, claims=Depends(current_user)):
    agent = Agent(tenant_id=claims["tenant_id"], **inp.model_dump())
    await db.agents.insert_one(agent.model_dump())
    return agent.model_dump()


@api.put("/agents/{agent_id}")
async def update_agent(agent_id: str, inp: AgentInput, claims=Depends(current_user)):
    res = await db.agents.update_one(
        {"id": agent_id, "tenant_id": claims["tenant_id"]},
        {"$set": inp.model_dump()},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Agente não encontrado")
    return await db.agents.find_one({"id": agent_id}, {"_id": 0})


@api.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, claims=Depends(current_user)):
    await db.agents.delete_one({"id": agent_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


@api.post("/agents/{agent_id}/test")
async def test_agent(agent_id: str, inp: SendMessageInput, claims=Depends(current_user)):
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    ok, err = _agent_is_configured(agent)
    if not ok:
        raise HTTPException(400, err)
    session = f"test-{agent_id}"
    ap, ak = agent.get("api_provider", "emergent"), agent.get("api_key", "")
    try:
        intent = await classify_intent(inp.text, session, ap, ak)
        structure = await structure_message(inp.text, "webchat", session, ap, ak)
        retrieved = await retrieve(db, claims["tenant_id"], inp.text, k=6, source_ids=agent.get("data_source_ids") or None)
        decision = decide_actions(intent, structure, agent)
        lang = _detect(inp.text, agent.get("default_language", "pt"))
        reply = await generate_response(agent, [{"sender": "user", "text": inp.text}], intent, structure, retrieved, lang, session)
    except LLMConfigMissing as e:
        raise HTTPException(400, str(e))
    except LLMProviderError as e:
        raise HTTPException(502, str(e))
    return {"intent": intent, "structure": structure, "decision": decision,
            "retrieved": [{"kind": d.get("kind", "item"), "meta": d.get("meta", {}), "text": d["text"][:200]} for d in retrieved],
            "language": lang, **reply}


@api.post("/agents/{agent_id}/test-email")
async def agent_test_email(agent_id: str, body: dict, claims=Depends(current_user)):
    """Send a test email using the agent's SMTP config."""
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    cfg = agent.get("email") or {}
    if not cfg.get("host") or not cfg.get("from_email"):
        return {"ok": False, "error": "Configuração SMTP incompleta. Preencha servidor e email remetente."}
    to = (body or {}).get("to") or cfg.get("notify_email") or cfg.get("from_email")
    if not to:
        return {"ok": False, "error": "Indique um destinatário"}
    html = f"<p>Olá! Este é um email de teste do agente <b>{agent.get('name','')}</b> no Consenso+.</p>"
    return send_email(cfg, to, f"Consenso+ · Teste · {agent.get('name','')}", html)


@api.post("/agents/{agent_id}/test-channel/{channel}")
async def agent_test_channel(agent_id: str, channel: str, claims=Depends(current_user)):
    """Validate a channel configuration by calling its provider API."""
    import httpx
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    ch = (agent.get("channels") or {}).get(channel) or {}
    if not ch.get("enabled"):
        return {"ok": False, "error": "Canal desativado. Ative primeiro."}

    try:
        if channel == "webchat":
            return {"ok": True, "info": "Widget do agente pronto para instalação."}

        if channel == "telegram":
            token = (ch.get("bot_token") or "").strip()
            if not token:
                return {"ok": False, "error": "Bot Token em falta"}
            async with httpx.AsyncClient(timeout=10) as hc:
                r = await hc.get(f"https://api.telegram.org/bot{token}/getMe")
            if r.status_code != 200:
                return {"ok": False, "error": f"Telegram rejeitou o token (HTTP {r.status_code})"}
            j = r.json()
            if not j.get("ok"):
                return {"ok": False, "error": j.get("description") or "Token inválido"}
            info = j.get("result", {})
            return {"ok": True, "info": f"@{info.get('username','?')} · {info.get('first_name','')}"}

        if channel == "whatsapp":
            tok = (ch.get("access_token") or "").strip()
            pid = (ch.get("phone_number_id") or "").strip()
            if not tok or not pid:
                return {"ok": False, "error": "Access Token e Phone Number ID obrigatórios"}
            async with httpx.AsyncClient(timeout=10) as hc:
                r = await hc.get(
                    f"https://graph.facebook.com/v20.0/{pid}",
                    params={"fields": "display_phone_number,verified_name"},
                    headers={"Authorization": f"Bearer {tok}"},
                )
            if r.status_code != 200:
                try:
                    msg = r.json().get("error", {}).get("message", "Erro desconhecido")
                except Exception:
                    msg = f"HTTP {r.status_code}"
                return {"ok": False, "error": f"WhatsApp: {msg}"}
            j = r.json()
            return {"ok": True, "info": f"{j.get('verified_name','')} · {j.get('display_phone_number','')}"}

        return {"ok": False, "error": f"Canal não suportado: {channel}"}
    except Exception as e:
        return {"ok": False, "error": f"Erro de ligação: {str(e)[:200]}"}


# ======================== DATA SOURCES ========================
@api.get("/data-sources")
async def list_sources(claims=Depends(current_user)):
    return await db.data_sources.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.post("/data-sources/url")
async def add_url_source(inp: DataSourceURLInput, claims=Depends(current_user)):
    src_id = new_id()
    doc = {
        "id": src_id, "tenant_id": claims["tenant_id"], "kind": "url",
        "name": inp.name, "url": inp.url, "status": "pending",
        "chunks": 0, "items": 0, "last_indexed_at": None, "error": None,
        "created_at": now_iso(),
    }
    await db.data_sources.insert_one(doc.copy())

    try:
        scraped = scrape_url(inp.url)
        chunks = build_chunks(src_id, claims["tenant_id"], scraped["title"], scraped["text"], scraped["items"])
        if chunks:
            await db.data_chunks.insert_many([c.copy() for c in chunks])
        await db.data_sources.update_one(
            {"id": src_id},
            {"$set": {"status": "indexed", "chunks": len(chunks),
                      "items": len(scraped["items"]), "last_indexed_at": now_iso()}},
        )
    except Exception as e:
        await db.data_sources.update_one(
            {"id": src_id},
            {"$set": {"status": "error", "error": str(e)[:400]}},
        )
    return await db.data_sources.find_one({"id": src_id}, {"_id": 0})


@api.post("/data-sources/text")
async def add_text_source(inp: DataSourceTextInput, claims=Depends(current_user)):
    src_id = new_id()
    chunks = build_chunks(src_id, claims["tenant_id"], inp.name, inp.text, [])
    doc = {
        "id": src_id, "tenant_id": claims["tenant_id"], "kind": "text",
        "name": inp.name, "url": None, "status": "indexed",
        "chunks": len(chunks), "items": 0, "last_indexed_at": now_iso(), "error": None,
        "created_at": now_iso(),
    }
    await db.data_sources.insert_one(doc.copy())
    if chunks:
        await db.data_chunks.insert_many([c.copy() for c in chunks])
    return doc


@api.post("/data-sources/file")
async def add_file_source(
    claims=Depends(current_user),
    file: UploadFile = File(...),
    name: str = Form(...),
):
    raw = await file.read()
    text = ""
    filename = (file.filename or "").lower()
    try:
        if filename.endswith(".pdf"):
            from io import BytesIO
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(raw))
            parts = []
            for page in reader.pages[:200]:
                try:
                    parts.append(page.extract_text() or "")
                except Exception:
                    pass
            text = "\n".join(parts)
        elif filename.endswith(".json"):
            import json as _json
            try:
                data = _json.loads(raw.decode("utf-8", errors="ignore"))
                text = _json.dumps(data, ensure_ascii=False, indent=2)
            except Exception:
                text = raw.decode("utf-8", errors="ignore")
        else:
            # .txt .md .csv and anything else treated as text
            text = raw.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(400, f"Falha a ler o ficheiro: {str(e)[:200]}")

    if not text.strip():
        raise HTTPException(400, "Ficheiro vazio ou ilegível")

    src_id = new_id()
    chunks = build_chunks(src_id, claims["tenant_id"], name, text, [])
    doc = {
        "id": src_id, "tenant_id": claims["tenant_id"], "kind": "file",
        "name": name, "url": file.filename, "status": "indexed",
        "chunks": len(chunks), "items": 0, "last_indexed_at": now_iso(), "error": None,
        "created_at": now_iso(),
    }
    await db.data_sources.insert_one(doc.copy())
    if chunks:
        await db.data_chunks.insert_many([c.copy() for c in chunks])
    return doc


@api.post("/data-sources/{src_id}/reindex")
async def reindex_source(src_id: str, claims=Depends(current_user)):
    src = await db.data_sources.find_one({"id": src_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not src:
        raise HTTPException(404, "Fonte não encontrada")
    await db.data_chunks.delete_many({"source_id": src_id})
    if src["kind"] == "url" and src.get("url"):
        try:
            scraped = scrape_url(src["url"])
            chunks = build_chunks(src_id, claims["tenant_id"], scraped["title"], scraped["text"], scraped["items"])
            if chunks:
                await db.data_chunks.insert_many([c.copy() for c in chunks])
            await db.data_sources.update_one(
                {"id": src_id},
                {"$set": {"status": "indexed", "chunks": len(chunks),
                          "items": len(scraped["items"]), "last_indexed_at": now_iso(), "error": None}},
            )
        except Exception as e:
            await db.data_sources.update_one({"id": src_id}, {"$set": {"status": "error", "error": str(e)[:400]}})
    return await db.data_sources.find_one({"id": src_id}, {"_id": 0})


@api.delete("/data-sources/{src_id}")
async def delete_source(src_id: str, claims=Depends(current_user)):
    await db.data_chunks.delete_many({"source_id": src_id, "tenant_id": claims["tenant_id"]})
    await db.data_sources.delete_one({"id": src_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


# ======================== CONVERSATIONS ========================
@api.get("/conversations")
async def list_conversations(
    claims=Depends(current_user),
    channel: Optional[str] = None,
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    q: Optional[str] = None,
):
    query: dict = {"tenant_id": claims["tenant_id"]}
    if channel and channel != "all":
        query["channel"] = channel
    if status and status != "all":
        query["status"] = status
    if agent_id and agent_id != "all":
        query["agent_id"] = agent_id
    if q:
        query["contact_name"] = {"$regex": q, "$options": "i"}
    convos = await db.conversations.find(query, {"_id": 0}).sort("last_message_at", -1).to_list(200)
    # Attach action counts (leads, tickets) linked to each conversation
    conv_ids = [c["id"] for c in convos]
    if conv_ids:
        lead_counts = {}
        tick_counts = {}
        async for l in db.leads.find({"conversation_id": {"$in": conv_ids}}, {"_id": 0, "conversation_id": 1}):
            lead_counts[l["conversation_id"]] = lead_counts.get(l["conversation_id"], 0) + 1
        async for t in db.tickets.find({"conversation_id": {"$in": conv_ids}}, {"_id": 0, "conversation_id": 1}):
            tick_counts[t["conversation_id"]] = tick_counts.get(t["conversation_id"], 0) + 1
        for c in convos:
            c["action_counts"] = {
                "leads": lead_counts.get(c["id"], 0),
                "tickets": tick_counts.get(c["id"], 0),
            }
    return convos


@api.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, claims=Depends(current_user),
                            limit: int = 100, before: Optional[str] = None):
    convo = await db.conversations.find_one({"id": conv_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not convo:
        raise HTTPException(404, "Não encontrada")
    # Paginate: fetch last `limit` messages older than `before` (ISO timestamp)
    q = {"conversation_id": conv_id}
    if before:
        q["created_at"] = {"$lt": before}
    total = await db.messages.count_documents({"conversation_id": conv_id})
    messages_desc = await db.messages.find(q, {"_id": 0}).sort("created_at", -1).limit(max(1, min(500, limit))).to_list(500)
    messages = list(reversed(messages_desc))
    # has_more = we fetched a full page (so older ones likely exist)
    has_more = len(messages_desc) >= limit and (total > len(messages) if not before else True)
    if not before:
        await db.conversations.update_one({"id": conv_id}, {"$set": {"unread": 0}})
    return {"conversation": convo, "messages": messages, "total": total, "has_more": bool(has_more)}


@api.post("/conversations/{conv_id}/takeover")
async def takeover(conv_id: str, claims=Depends(current_user)):
    res = await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$set": {"status": "human", "assigned_to": claims["sub"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Não encontrada")
    await ws_manager.broadcast(claims["tenant_id"], {"type": "conversation_update", "conversation_id": conv_id})
    return {"ok": True, "status": "human"}


@api.post("/conversations/{conv_id}/release")
async def release(conv_id: str, claims=Depends(current_user)):
    await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$set": {"status": "ai", "assigned_to": None}},
    )
    await ws_manager.broadcast(claims["tenant_id"], {"type": "conversation_update", "conversation_id": conv_id})
    return {"ok": True, "status": "ai"}


@api.post("/conversations/{conv_id}/close")
async def close_conv(conv_id: str, claims=Depends(current_user)):
    await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$set": {"status": "closed"}},
    )
    await ws_manager.broadcast(claims["tenant_id"], {"type": "conversation_update", "conversation_id": conv_id})
    return {"ok": True, "status": "closed"}


@api.post("/conversations/{conv_id}/messages")
async def send_human_message(conv_id: str, inp: SendMessageInput, claims=Depends(current_user)):
    convo = await db.conversations.find_one({"id": conv_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not convo:
        raise HTTPException(404, "Não encontrada")
    user_doc = await db.users.find_one({"id": claims["sub"]}, {"_id": 0})
    msg = {
        "id": new_id(), "tenant_id": claims["tenant_id"], "conversation_id": conv_id,
        "sender": "human", "sender_name": user_doc.get("name", "Agente") if user_doc else "Agente",
        "text": inp.text, "cards": [], "meta": {}, "created_at": now_iso(),
    }
    await db.messages.insert_one(msg.copy())
    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {"last_message": inp.text, "last_message_at": now_iso(),
                  "status": "human", "assigned_to": claims["sub"]}},
    )
    await ws_manager.broadcast(claims["tenant_id"], {"type": "message", "conversation_id": conv_id, "message": msg})
    return msg


@api.post("/conversations/{conv_id}/tag")
async def add_tag(conv_id: str, body: dict, claims=Depends(current_user)):
    tag = (body.get("tag") or "").strip().lower()
    if not tag:
        raise HTTPException(400, "tag obrigatória")
    await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$addToSet": {"tags": tag}},
    )
    return {"ok": True}


# ======================== INBOUND PIPELINE ========================
async def _process_inbound(tenant_id: str, inbound: InboundMessage, agent_id: Optional[str] = None) -> dict:
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    default_lang = (tenant or {}).get("default_language", "pt")

    convo = await db.conversations.find_one(
        {"tenant_id": tenant_id, "channel": inbound.channel,
         "external_user_id": inbound.external_user_id,
         "status": {"$ne": "closed"}},
        {"_id": 0},
    )
    if not convo:
        convo = {
            "id": new_id(), "tenant_id": tenant_id,
            "channel": inbound.channel, "external_user_id": inbound.external_user_id,
            "contact_name": inbound.contact_name, "contact_avatar": None,
            "status": "ai", "assigned_to": None, "agent_id": None,
            "tags": [], "language": default_lang, "last_message": inbound.text,
            "last_message_at": now_iso(), "unread": 1,
            "intent": None, "structure": None, "created_at": now_iso(),
        }
        await db.conversations.insert_one(convo.copy())

    conv_id = convo["id"]

    user_msg = {
        "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
        "sender": "user", "sender_name": inbound.contact_name,
        "text": inbound.text, "cards": [], "meta": {}, "created_at": now_iso(),
    }
    await db.messages.insert_one(user_msg.copy())
    await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": user_msg})

    if convo["status"] == "human":
        await db.conversations.update_one(
            {"id": conv_id},
            {"$set": {"last_message": inbound.text, "last_message_at": now_iso()},
             "$inc": {"unread": 1}},
        )
        return {"conversation_id": conv_id, "reply": None, "cards": [], "handoff": True}

    agent = None
    if agent_id:
        agent = await db.agents.find_one({"tenant_id": tenant_id, "id": agent_id, "active": True}, {"_id": 0})
    if not agent:
        agent = await db.agents.find_one({"tenant_id": tenant_id, "active": True}, {"_id": 0})
    if not agent:
        # No active agent — respond with a clear PT message
        ai_msg = {
            "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
            "sender": "ai", "sender_name": "Sistema",
            "text": "Nenhum agente IA ativo. Vá a Agentes IA e ative ou crie um agente.",
            "cards": [], "meta": {"error": "no_active_agent"}, "created_at": now_iso(),
        }
        await db.messages.insert_one(ai_msg.copy())
        await db.conversations.update_one({"id": conv_id}, {"$set": {"last_message": ai_msg["text"], "last_message_at": now_iso()}})
        await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": ai_msg})
        return {"conversation_id": conv_id, "reply": ai_msg["text"], "cards": [], "error": "no_active_agent"}

    ok, err = _agent_is_configured(agent)
    if not ok:
        ai_msg = {
            "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
            "sender": "ai", "sender_name": agent.get("name", "Sistema"),
            "text": err, "cards": [], "meta": {"error": "config_missing"}, "created_at": now_iso(),
        }
        await db.messages.insert_one(ai_msg.copy())
        await db.conversations.update_one({"id": conv_id}, {"$set": {"last_message": err, "last_message_at": now_iso()}})
        await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": ai_msg})
        return {"conversation_id": conv_id, "reply": err, "cards": [], "error": "config_missing"}

    session = f"conv-{conv_id}"
    ap, ak = agent.get("api_provider", "emergent"), agent.get("api_key", "")
    try:
        intent = await classify_intent(inbound.text, session, ap, ak)
        structure = await structure_message(inbound.text, inbound.channel, session, ap, ak)
    except (LLMConfigMissing, LLMProviderError) as e:
        ai_msg = {
            "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
            "sender": "ai", "sender_name": agent.get("name", "Sistema"),
            "text": str(e), "cards": [], "meta": {"error": "llm_failure"}, "created_at": now_iso(),
        }
        await db.messages.insert_one(ai_msg.copy())
        await db.conversations.update_one({"id": conv_id}, {"$set": {"last_message": str(e), "last_message_at": now_iso()}})
        await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": ai_msg})
        return {"conversation_id": conv_id, "reply": str(e), "cards": [], "error": "llm_failure"}
    retrieved = await retrieve(db, tenant_id, inbound.text, k=6, source_ids=agent.get("data_source_ids") or None)
    decision = decide_actions(intent, structure, agent)
    lang = _detect(inbound.text, agent.get("default_language", default_lang))

    history = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(20)
    try:
        resp = await generate_response(agent, history, intent, structure, retrieved, lang, session)
    except (LLMConfigMissing, LLMProviderError) as e:
        resp = {"reply": str(e), "cards": [], "language": lang}

    # Auto-tag lead from structure
    auto_tags = []
    if structure.get("domain") == "sales":
        auto_tags.append("sales")
    if structure.get("priority") in {"high", "urgent"}:
        auto_tags.append(structure.get("priority"))
    if intent.get("intent"):
        auto_tags.append(intent["intent"])

    action_results = await execute_actions(db, tenant_id, conv_id, decision.get("actions", []))
    # Attach tags + send email notification for AI-created leads
    for a in action_results:
        if a.get("tool") == "create_lead" and a.get("ok"):
            await db.leads.update_one({"id": a["id"]}, {"$set": {"tags": list(set(auto_tags))}})
            await _notify_new_lead(tenant_id, a["id"], agent)

    ai_msg = {
        "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
        "sender": "ai", "sender_name": agent.get("name", "AI"),
        "text": resp["reply"], "cards": resp.get("cards", []),
        "meta": {"intent": intent, "actions": action_results, "language": lang},
        "created_at": now_iso(),
    }
    await db.messages.insert_one(ai_msg.copy())

    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {
            "last_message": resp["reply"], "last_message_at": now_iso(),
            "intent": intent, "structure": structure, "agent_id": agent.get("id"),
            "status": "ai", "language": lang,
            "tags": list(set((convo.get("tags") or []) + auto_tags)),
        }, "$inc": {"unread": 1}},
    )

    await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": ai_msg})

    return {
        "conversation_id": conv_id,
        "reply": resp["reply"],
        "cards": resp.get("cards", []),
        "intent": intent, "structure": structure,
        "actions": action_results, "language": lang,
    }


@api.post("/webchat/{tenant_id}/message")
async def webchat_inbound(tenant_id: str, inbound: InboundMessage):
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")
    inbound.channel = "webchat"
    return await _process_inbound(tenant_id, inbound, agent_id=inbound.agent_id)


@api.post("/inbound/simulate")
async def simulate_inbound(inbound: InboundMessage, claims=Depends(current_user)):
    return await _process_inbound(claims["tenant_id"], inbound, agent_id=inbound.agent_id)


# ======================== LEADS ========================
@api.get("/leads")
async def list_leads(claims=Depends(current_user)):
    return await db.leads.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/leads")
async def create_lead(inp: LeadInput, claims=Depends(current_user)):
    lead = Lead(tenant_id=claims["tenant_id"], **inp.model_dump())
    await db.leads.insert_one(lead.model_dump())
    return lead.model_dump()


@api.put("/leads/{lead_id}")
async def update_lead(lead_id: str, inp: LeadInput, claims=Depends(current_user)):
    res = await db.leads.update_one(
        {"id": lead_id, "tenant_id": claims["tenant_id"]},
        {"$set": inp.model_dump()},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Não encontrado")
    return await db.leads.find_one({"id": lead_id}, {"_id": 0})


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, claims=Depends(current_user)):
    await db.leads.delete_one({"id": lead_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


@api.post("/leads/{lead_id}/sync-crm")
async def sync_crm(lead_id: str, claims=Depends(current_user)):
    """Stub CRM sync - marks lead as synced. Real HubSpot/Pipedrive/Salesforce API
    wiring happens once the tenant connects a CRM in Integrations."""
    lead = await db.leads.find_one({"id": lead_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Não encontrado")
    await db.leads.update_one({"id": lead_id}, {"$set": {"crm_synced": True}})
    return {"ok": True, "synced": True}


# ======================== TICKETS ========================
@api.get("/tickets")
async def list_tickets(claims=Depends(current_user)):
    return await db.tickets.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.post("/tickets")
async def create_ticket(inp: TicketInput, claims=Depends(current_user)):
    ticket = Ticket(tenant_id=claims["tenant_id"], **inp.model_dump())
    await db.tickets.insert_one(ticket.model_dump())
    return ticket.model_dump()


@api.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, inp: TicketInput, claims=Depends(current_user)):
    res = await db.tickets.update_one(
        {"id": ticket_id, "tenant_id": claims["tenant_id"]},
        {"$set": inp.model_dump()},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Não encontrado")
    return await db.tickets.find_one({"id": ticket_id}, {"_id": 0})


@api.delete("/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str, claims=Depends(current_user)):
    await db.tickets.delete_one({"id": ticket_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


# ======================== INTEGRATIONS ========================
@api.get("/integrations")
async def list_integrations(claims=Depends(current_user)):
    return await db.integrations.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).to_list(200)


@api.put("/integrations/{int_id}")
async def update_integration(int_id: str, body: dict, claims=Depends(current_user)):
    current = await db.integrations.find_one({"id": int_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not current:
        raise HTTPException(404, "Não encontrado")
    allowed = {k: v for k, v in body.items() if k in {"status", "config", "name"}}
    # Validate config when trying to connect
    next_status = allowed.get("status", current.get("status"))
    next_cfg = {**(current.get("config") or {}), **(allowed.get("config") or {})}
    if allowed.get("config") is not None:
        allowed["config"] = next_cfg
    if next_status == "connected":
        kind = current["kind"]
        required = {
            "whatsapp": ["access_token", "phone_number_id"],
            "instagram": ["access_token", "page_id"],
            "telegram": ["bot_token"],
            "messenger": ["access_token", "page_id"],
            "webchat": [],
            "smtp": ["host", "port", "from_email"],
            "hubspot": [], "pipedrive": [], "salesforce": [], "webhook": ["url"],
        }.get(kind, [])
        missing = []
        for k in required:
            v = next_cfg.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                missing.append(k)
        if missing:
            raise HTTPException(400, f"Configuração incompleta. Campos em falta: {', '.join(missing)}")
    await db.integrations.update_one({"id": int_id, "tenant_id": claims["tenant_id"]}, {"$set": allowed})
    return await db.integrations.find_one({"id": int_id}, {"_id": 0})


@api.post("/integrations/{int_id}/test-email")
async def integration_test_email(int_id: str, body: dict, claims=Depends(current_user)):
    it = await db.integrations.find_one({"id": int_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not it or it["kind"] != "smtp":
        raise HTTPException(400, "Integração SMTP não encontrada")
    to = body.get("to") or it.get("config", {}).get("from_email")
    if not to:
        raise HTTPException(400, "Indique um destinatário")
    html = "<p>Olá! Este é um email de teste enviado pelo Consenso Plus. ✔</p>"
    result = send_email(it.get("config") or {}, to, "Consenso Plus · Email de teste", html)
    return result


# ======================== TEAM ========================
@api.get("/team")
async def list_team(claims=Depends(current_user)):
    return await db.users.find(
        {"tenant_id": claims["tenant_id"]},
        {"_id": 0, "password_hash": 0},
    ).to_list(200)


@api.post("/team/invite")
async def invite_member(inv: TeamInvite, claims=Depends(current_user)):
    existing = await db.users.find_one({"email": inv.email}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Email já existe")
    user = {
        "id": new_id(), "tenant_id": claims["tenant_id"],
        "email": inv.email, "name": inv.name, "role": inv.role,
        "password_hash": hash_password(inv.password),
        "created_at": now_iso(),
    }
    await db.users.insert_one(user.copy())
    user.pop("password_hash", None)
    return user


@api.delete("/team/{user_id}")
async def remove_member(user_id: str, claims=Depends(current_user)):
    if user_id == claims["sub"]:
        raise HTTPException(400, "Não pode remover-se a si próprio")
    await db.users.delete_one({"id": user_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


# ======================== PLATFORM ADMIN ========================
@api.get("/admin/tenants")
async def list_all_tenants(claims=Depends(current_user)):
    if claims.get("role") != "platform_admin":
        tenants = await db.tenants.find({"id": claims["tenant_id"]}, {"_id": 0}).to_list(1)
    else:
        tenants = await db.tenants.find({}, {"_id": 0}).to_list(500)
    result = []
    for t in tenants:
        users = await db.users.count_documents({"tenant_id": t["id"]})
        convos = await db.conversations.count_documents({"tenant_id": t["id"]})
        leads = await db.leads.count_documents({"tenant_id": t["id"]})
        result.append({**t, "users": users, "conversations": convos, "leads": leads})
    return result


# ======================== PUBLIC AGENT IDENTITY ========================
@api.get("/public/agent/{tenant_id}")
async def public_agent(tenant_id: str, agent_id: Optional[str] = None):
    """Public endpoint used by the embed widget to fetch agent identity (no auth)."""
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")
    query = {"tenant_id": tenant_id, "active": True}
    if agent_id:
        query["id"] = agent_id
    agent = await db.agents.find_one(query, {"_id": 0, "api_key": 0, "rules": 0, "system_prompt": 0, "knowledge": 0})
    if not agent:
        return {
            "tenant_name": tenant.get("name"),
            "name": "Assistente", "avatar_url": "", "welcome_message": "Olá! Como posso ajudar?",
            "icebreakers": [], "language": tenant.get("default_language", "pt"),
        }
    return {
        "agent_id": agent["id"], "tenant_name": tenant.get("name"),
        "name": agent.get("name", "Assistente"),
        "avatar_url": agent.get("avatar_url", ""),
        "welcome_message": agent.get("welcome_message") or "Olá! Como posso ajudar?",
        "icebreakers": agent.get("icebreakers") or [],
        "language": agent.get("default_language", "pt"),
    }


# ======================== WEBSOCKET ========================
@app.websocket("/api/ws/{tenant_id}")
async def ws_endpoint(websocket: WebSocket, tenant_id: str):
    await ws_manager.connect(tenant_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(tenant_id, websocket)


# ======================== EMBEDDABLE WIDGET ========================
_WIDGET_PATH = ROOT_DIR / "widget.html"


def _load_widget() -> str:
    try:
        return _WIDGET_PATH.read_text(encoding="utf-8")
    except Exception:
        return "<html><body>Widget not found</body></html>"


@api.get("/widget/{tenant_id}", response_class=HTMLResponse)
async def widget_api(tenant_id: str):
    return HTMLResponse(_load_widget())


_WIDGET_JS_PATH = ROOT_DIR / "widget.js"


@api.get("/widget.js")
async def widget_js_api():
    from fastapi.responses import Response
    try:
        content = _WIDGET_JS_PATH.read_text(encoding="utf-8")
    except Exception:
        content = "/* widget.js not found */"
    return Response(content=content, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=300",
                             "Access-Control-Allow-Origin": "*"})


@api.get("/brand-icon.png")
async def brand_icon():
    from fastapi.responses import Response
    path = ROOT_DIR / "static" / "consenso-icon.png"
    try:
        return Response(content=path.read_bytes(), media_type="image/png",
                        headers={"Cache-Control": "public, max-age=86400",
                                 "Access-Control-Allow-Origin": "*"})
    except Exception:
        raise HTTPException(404)


@api.get("/widget-test/{tenant_id}/{agent_id}", response_class=HTMLResponse)
async def widget_test_page(tenant_id: str, agent_id: str, request: Request):
    """Demo page that loads widget.js as an external site would — for real-world testing."""
    # Derive public URL from forwarded headers so the displayed snippet matches what the user will paste
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    proto = request.headers.get("x-forwarded-proto") or ("https" if request.url.scheme == "https" else "http")
    backend = f"{proto}://{host}"
    # Use relative /api/widget.js so it works regardless of deployment
    html = f"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<title>Consenso+ · Página de teste</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}}body{{margin:0;font-family:Inter,system-ui,sans-serif;color:#0B1324;background:linear-gradient(180deg,#F7F9FC 0%,#EAF2FF 100%);min-height:100vh}}
.wrap{{max-width:780px;margin:0 auto;padding:60px 24px}}
.badge{{display:inline-block;background:#0069FE;color:#fff;padding:4px 12px;border-radius:999px;font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase}}
h1{{font-size:40px;font-weight:700;letter-spacing:-.02em;margin:16px 0 8px}}
p{{color:#5B6B82;font-size:16px;line-height:1.6;margin:0 0 12px}}
.card{{background:#fff;border:1px solid #E5EAF2;border-radius:16px;padding:28px;margin-top:32px;box-shadow:0 2px 10px rgba(11,19,36,.04)}}
.card h2{{font-size:18px;margin:0 0 8px}}
.arrow{{position:fixed;bottom:100px;right:28px;background:#0B1324;color:#fff;padding:10px 16px;border-radius:12px;font-size:13px;font-weight:600;animation:b 1.2s infinite}}
.arrow::after{{content:"";position:absolute;bottom:-7px;right:25px;width:0;height:0;border:8px solid transparent;border-top-color:#0B1324;border-bottom:0}}
@keyframes b{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-4px)}}}}
code{{background:#F7F9FC;padding:2px 6px;border-radius:4px;font-size:13px;color:#0069FE}}
</style>
</head>
<body>
<div class="wrap">
<span class="badge">Página de teste</span>
<h1>O seu chatbot em ação</h1>
<p>Esta é uma página de teste que carrega o mesmo script que o seu cliente vai colar no site dele.</p>
<p>Deverá ver o <b>ícone azul flutuante</b> no canto inferior direito. Clique para abrir o chat.</p>

<div class="card">
<h2>Script instalado</h2>
<p style="font-family:monospace;font-size:12px;background:#F7F9FC;padding:12px;border-radius:8px;white-space:pre-wrap;color:#0B1324">&lt;script src="{backend}/api/widget.js"
  data-tenant-id="{tenant_id}"
  data-agent-id="{agent_id}"
  defer&gt;&lt;/script&gt;</p>
</div>

<div class="card">
<h2>Como testar</h2>
<p>1. Verifique que o ícone azul apareceu no canto inferior direito.</p>
<p>2. Clique no ícone — deve abrir a janela de chat.</p>
<p>3. Escreva uma mensagem de cliente (ex: <code>Olá, tenho uma questão</code>).</p>
<p>4. A IA responde com o agente configurado.</p>
</div>
</div>
<div class="arrow">O ícone aparece aqui ↓</div>
<script src="/api/widget.js" data-tenant-id="{tenant_id}" data-agent-id="{agent_id}" defer></script>
</body>
</html>"""
    return HTMLResponse(html)


# ======================== ROOT ========================
@api.get("/")
async def root():
    return {"name": "Consenso Plus", "version": "2.3.0", "status": "ok"}


app.include_router(api)
app.include_router(build_webhooks_router(db, _process_inbound))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")


@app.on_event("shutdown")
async def _shutdown():
    client.close()
