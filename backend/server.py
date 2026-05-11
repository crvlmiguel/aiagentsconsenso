"""Consenso Plus — AI Business Operating System (multi-tenant SaaS backend)."""
import os
import asyncio
import logging
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request, Body
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
from ai.analyze import analyze_message
from ai.orchestrator import decide_actions, generate_response
from ai.qualify import qualify_conversation
from ai.tools import execute_actions
from ai.retrieval import scrape_url, build_chunks, retrieve
from ai.router import test_connection as llm_test_connection, LLMConfigMissing, LLMProviderError
from email_service import send_email, render_lead_email
from ws_manager import manager as ws_manager
from webhooks import build_router as build_webhooks_router
from ai.finance import (
    detect_finance_intent, extract_price_from_text,
    calcular_prestacao, format_simulation_pt, extract_credit_params,
    calcular_comparacao,
)
from ai.lead_score import compute_lead_score
import follow_up as follow_up_module
import property_feed as property_feed_module

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
    score = lead.get("score") or 0
    tier_icon = "🔥" if score >= 70 else ("🌡️" if score >= 40 else "❄️")
    subject = f"{tier_icon} Novo lead · {lead.get('name', '')} (score {score})"
    result = send_email(email_cfg, to, subject, html)
    logger.info(f"Lead email notify {lead_id} → {to}: {result}")
    await db.leads.update_one({"id": lead_id}, {"$set": {"email_notified": bool(result.get("ok"))}})


async def _recompute_lead_score(lead_id: str) -> None:
    """Recalcula o score 0-100 de um lead com base na conversa associada."""
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead:
        return
    convo = None
    history = []
    if lead.get("conversation_id"):
        convo = await db.conversations.find_one({"id": lead["conversation_id"]}, {"_id": 0})
        history = await db.messages.find(
            {"conversation_id": lead["conversation_id"]}, {"_id": 0}
        ).sort("created_at", 1).to_list(50)
    res = compute_lead_score(convo, lead, history)
    await db.leads.update_one(
        {"id": lead_id},
        {"$set": {"score": res["score"], "score_tier": res["tier"], "score_signals": res["signals"]}},
    )


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
    if not tenant:
        raise HTTPException(500, "Tenant não encontrado")
    # Defensive: backfill missing fields on legacy/incomplete tenant docs so
    # Pydantic response model never raises a ValidationError → 500.
    backfill = {}
    if not tenant.get("slug"):
        backfill["slug"] = (tenant.get("name") or "tenant").lower().replace(" ", "-")[:32]
    if not tenant.get("plan"):
        backfill["plan"] = "pro"
    if backfill:
        await db.tenants.update_one({"id": tenant["id"]}, {"$set": backfill})
        tenant.update(backfill)
    if user.get("role") not in {"owner", "admin", "agent", "platform_admin"}:
        await db.users.update_one({"id": user["id"]}, {"$set": {"role": "owner"}})
        user["role"] = "owner"
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
    # BYO providers — accept either the per-agent api_key OR the corresponding env var
    # (e.g. OPENAI_API_KEY) so platform-managed keys can power agents without manual paste.
    has_key = bool((agent.get("api_key") or "").strip())
    env_keys = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}
    has_env = bool(os.environ.get(env_keys.get(prov, ""), ""))
    if not has_key and not has_env:
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


# ======================== ANALYTICS (per-agent) ========================
@api.get("/agents/{agent_id}/analytics")
async def agent_analytics(agent_id: str, days: int = 30, claims=Depends(current_user)):
    """Advanced per-agent analytics for the dashboard:
      - conversations, messages, leads totals + daily breakdown
      - conversion_rate (leads / conversations)
      - qualification_breakdown (quente/morno/frio)
      - top_icebreakers (which opening messages led to leads)
      - funnel: visitors → engaged (3+ msgs) → qualified → lead_captured

    Returns empty-but-valid shapes when there's no data yet.
    """
    from datetime import timedelta, datetime, timezone
    days = max(1, min(int(days) if days is not None else 30, 365))
    tid = claims["tenant_id"]
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": tid}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # ---- Totals
    convo_q = {"tenant_id": tid, "agent_id": agent_id, "created_at": {"$gte": cutoff}}
    convos_total = await db.conversations.count_documents(convo_q)

    leads_q = {"tenant_id": tid, "agent_id": agent_id, "created_at": {"$gte": cutoff}}
    leads_total = await db.leads.count_documents(leads_q)

    # Messages — joined via conversation_id
    convo_ids = [c["id"] async for c in db.conversations.find(convo_q, {"id": 1, "_id": 0})]
    msg_q = {"conversation_id": {"$in": convo_ids}} if convo_ids else {"conversation_id": "__none__"}
    messages_total = await db.messages.count_documents(msg_q)

    conversion_rate = round((leads_total / convos_total) * 100, 1) if convos_total else 0.0

    # ---- Daily breakdown (conversations + leads)
    def _day(iso: str) -> str:
        return (iso or "")[:10]
    daily_convos = {}
    async for c in db.conversations.find(convo_q, {"created_at": 1, "_id": 0}):
        d = _day(c.get("created_at", ""))
        if d: daily_convos[d] = daily_convos.get(d, 0) + 1
    daily_leads = {}
    async for l in db.leads.find(leads_q, {"created_at": 1, "_id": 0}):
        d = _day(l.get("created_at", ""))
        if d: daily_leads[d] = daily_leads.get(d, 0) + 1
    # Fill missing days
    today = datetime.now(timezone.utc).date()
    daily_series = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        daily_series.append({
            "day": d,
            "conversations": daily_convos.get(d, 0),
            "leads": daily_leads.get(d, 0),
        })

    # ---- Qualification breakdown (uses convo.qualification.status / .tags)
    qual = {"quente": 0, "morno": 0, "frio": 0, "outros": 0}
    async for c in db.conversations.find(convo_q, {"qualification": 1, "tags": 1, "_id": 0}):
        q = (c.get("qualification") or {})
        status = (q.get("status") or "").lower()
        tags = [t.lower() for t in (c.get("tags") or [])]
        score = "outros"
        if "quente" in status or "quente" in tags or "hot" in tags or "high" in status:
            score = "quente"
        elif "morno" in status or "morno" in tags or "warm" in tags or "medium" in status:
            score = "morno"
        elif "frio" in status or "frio" in tags or "cold" in tags or "low" in status:
            score = "frio"
        qual[score] += 1

    # ---- Top icebreakers — counts of first user message that led to a lead
    icebreaker_to_leads = {}
    icebreaker_total = {}
    if convo_ids:
        # For each conversation, get the first user message text
        async for m in db.messages.aggregate([
            {"$match": {"conversation_id": {"$in": convo_ids}, "sender": "user"}},
            {"$sort": {"created_at": 1}},
            {"$group": {"_id": "$conversation_id", "first_text": {"$first": "$text"}}},
        ]):
            text = (m.get("first_text") or "").strip()[:120]
            if not text:
                continue
            icebreaker_total[text] = icebreaker_total.get(text, 0) + 1
        # Tag which conversations had a lead
        lead_convo_ids = set()
        async for l in db.leads.find(leads_q, {"conversation_id": 1, "_id": 0}):
            if l.get("conversation_id"):
                lead_convo_ids.add(l["conversation_id"])
        # Re-aggregate but only for lead-producing conversations
        if lead_convo_ids:
            async for m in db.messages.aggregate([
                {"$match": {"conversation_id": {"$in": list(lead_convo_ids)}, "sender": "user"}},
                {"$sort": {"created_at": 1}},
                {"$group": {"_id": "$conversation_id", "first_text": {"$first": "$text"}}},
            ]):
                text = (m.get("first_text") or "").strip()[:120]
                if not text:
                    continue
                icebreaker_to_leads[text] = icebreaker_to_leads.get(text, 0) + 1

    top_icebreakers = sorted([
        {"opener": k, "opens": v, "leads": icebreaker_to_leads.get(k, 0),
         "rate": round((icebreaker_to_leads.get(k, 0) / v) * 100, 1) if v else 0.0}
        for k, v in icebreaker_total.items()
    ], key=lambda x: (-x["leads"], -x["opens"]))[:8]

    # ---- Funnel
    # visitors = unique external_user_id with at least 1 msg
    visitors = await db.conversations.count_documents(convo_q)
    # engaged = convo with >= 3 messages (user msgs >= 2)
    engaged = 0
    if convo_ids:
        async for grp in db.messages.aggregate([
            {"$match": {"conversation_id": {"$in": convo_ids}, "sender": "user"}},
            {"$group": {"_id": "$conversation_id", "n": {"$sum": 1}}},
            {"$match": {"n": {"$gte": 2}}},
            {"$count": "engaged"},
        ]):
            engaged = grp.get("engaged", 0)
    qualified = sum(qual[k] for k in ("quente", "morno"))  # quente + morno
    funnel = [
        {"stage": "Visitantes", "value": visitors},
        {"stage": "Engajados (3+ msgs)", "value": engaged},
        {"stage": "Qualificados", "value": qualified},
        {"stage": "Leads capturados", "value": leads_total},
    ]

    return {
        "agent_id": agent_id,
        "agent_name": agent.get("name"),
        "days": days,
        "totals": {
            "conversations": convos_total,
            "messages": messages_total,
            "leads": leads_total,
            "conversion_rate": conversion_rate,
        },
        "daily_series": daily_series,
        "qualification_breakdown": qual,
        "top_icebreakers": top_icebreakers,
        "funnel": funnel,
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
        # Parallelize analyze + retrieve — both depend only on inp.text. Saves ~1-2s.
        import asyncio
        (intent, structure), retrieved = await asyncio.gather(
            analyze_message(inp.text, "webchat", session, ap, ak),
            retrieve(db, claims["tenant_id"], inp.text, k=6, source_ids=agent.get("data_source_ids") or None),
        )
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


@api.post("/agents/{agent_id}/avatar")
async def agent_upload_avatar(agent_id: str, file: UploadFile = File(...), claims=Depends(current_user)):
    """Upload agent avatar image. Returns data URL for instant display."""
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, "Ficheiro não é uma imagem")
    raw = await file.read()
    if len(raw) > 2 * 1024 * 1024:
        raise HTTPException(400, "Imagem demasiado grande (máx 2MB)")
    import base64
    data_url = f"data:{file.content_type};base64,{base64.b64encode(raw).decode('ascii')}"
    await db.agents.update_one({"id": agent_id}, {"$set": {"avatar_url": data_url}})
    return {"ok": True, "avatar_url": data_url}


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
    """Validate a channel configuration by calling its provider API.
    Persists the result on agent.channels.{channel}.last_test_* so the health dashboard
    can show the most recent handshake without re-pinging providers."""
    import httpx
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    ch = (agent.get("channels") or {}).get(channel) or {}
    if not ch.get("enabled"):
        return {"ok": False, "error": "Canal desativado. Ative primeiro."}

    result: dict = {"ok": False, "error": "Canal não suportado"}
    try:
        result = await _run_channel_test(channel, ch)
    except Exception as e:
        result = {"ok": False, "error": f"Erro de ligação: {str(e)[:200]}"}

    # Persist last handshake state for the health dashboard.
    try:
        await db.agents.update_one(
            {"id": agent_id, "tenant_id": claims["tenant_id"]},
            {"$set": {
                f"channels.{channel}.last_test_at": now_iso(),
                f"channels.{channel}.last_test_ok": bool(result.get("ok")),
                f"channels.{channel}.last_test_info": (result.get("info") or "")[:240],
                f"channels.{channel}.last_test_error": (result.get("error") or "")[:240],
            }},
        )
    except Exception as e:
        logger.warning(f"Could not persist last_test state: {e}")
    return result


async def _run_channel_test(channel: str, ch: dict) -> dict:
    """Pure provider call — no DB writes. Returns {ok, info?, error?}."""
    import httpx
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

    if channel == "messenger":
        tok = (ch.get("page_access_token") or "").strip()
        pid = (ch.get("page_id") or "").strip()
        if not tok or not pid:
            return {"ok": False, "error": "Page Access Token e Page ID obrigatórios"}
        async with httpx.AsyncClient(timeout=10) as hc:
            r = await hc.get(
                f"https://graph.facebook.com/v20.0/{pid}",
                params={"fields": "name,id,category", "access_token": tok},
            )
        if r.status_code != 200:
            try:
                msg = r.json().get("error", {}).get("message", "Erro desconhecido")
            except Exception:
                msg = f"HTTP {r.status_code}"
            return {"ok": False, "error": f"Messenger: {msg}"}
        j = r.json()
        return {"ok": True, "info": f"{j.get('name','?')} · {j.get('category','Page')} (id={j.get('id','')})"}

    if channel == "instagram":
        tok = (ch.get("page_access_token") or "").strip()
        iid = (ch.get("ig_user_id") or "").strip()
        if not tok or not iid:
            return {"ok": False, "error": "Page Access Token e IG User ID obrigatórios"}
        async with httpx.AsyncClient(timeout=10) as hc:
            r = await hc.get(
                f"https://graph.facebook.com/v20.0/{iid}",
                params={"fields": "username,name,profile_picture_url", "access_token": tok},
            )
        if r.status_code != 200:
            try:
                msg = r.json().get("error", {}).get("message", "Erro desconhecido")
            except Exception:
                msg = f"HTTP {r.status_code}"
            return {"ok": False, "error": f"Instagram: {msg}"}
        j = r.json()
        return {"ok": True, "info": f"@{j.get('username','?')} · {j.get('name','')}"}

    return {"ok": False, "error": f"Canal não suportado: {channel}"}


# ======================== AGENT HEALTH (omni-canal dashboard) ========================
@api.get("/agents/health")
async def agents_health(claims=Depends(current_user)):
    """Aggregated health view for the dashboard. Returns a list of agents with each
    channel's enabled/configured/last-handshake state. Read-only — does not call providers.
    Use POST /agents/{id}/test-channel/{channel} to refresh the handshake."""
    SOCIAL = ("webchat", "whatsapp", "telegram", "instagram", "messenger")
    REQUIRED_FIELDS = {
        "webchat": (),
        "whatsapp": ("access_token", "phone_number_id"),
        "telegram": ("bot_token",),
        "instagram": ("page_access_token", "ig_user_id"),
        "messenger": ("page_access_token", "page_id"),
    }
    cursor = db.agents.find(
        {"tenant_id": claims["tenant_id"], "active": True},
        {"_id": 0, "id": 1, "name": 1, "avatar_url": 1, "channels": 1, "tenant_id": 1, "theme": 1},
    )
    agents = await cursor.to_list(200)
    out = []
    for a in agents:
        chs = (a.get("channels") or {})
        items = []
        for k in SOCIAL:
            cfg = chs.get(k) or {}
            enabled = bool(cfg.get("enabled"))
            req = REQUIRED_FIELDS.get(k, ())
            configured = bool(req == () or all(str(cfg.get(f) or "").strip() for f in req))
            items.append({
                "channel": k,
                "enabled": enabled,
                "configured": configured,
                "last_test_at": cfg.get("last_test_at"),
                "last_test_ok": cfg.get("last_test_ok"),
                "last_test_info": cfg.get("last_test_info") or "",
                "last_test_error": cfg.get("last_test_error") or "",
            })
        out.append({
            "id": a["id"],
            "name": a.get("name") or "",
            "avatar_url": a.get("avatar_url") or "",
            "tenant_id": a.get("tenant_id"),
            "channels": items,
        })
    return out


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


@api.post("/conversations/{conv_id}/qualify")
async def refresh_qualification(conv_id: str, claims=Depends(current_user)):
    """Recalcula a qualificação CRM a pedido (botão refresh na UI)."""
    convo = await db.conversations.find_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]}, {"_id": 0}
    )
    if not convo:
        raise HTTPException(404, "Conversa não encontrada")

    history = await db.messages.find(
        {"conversation_id": conv_id}, {"_id": 0}
    ).sort("created_at", 1).to_list(200)

    agent = await db.agents.find_one({"id": convo.get("agent_id")}, {"_id": 0}) if convo.get("agent_id") else None
    ap = (agent or {}).get("api_provider", "emergent")
    ak = (agent or {}).get("api_key", "")

    qualification = await qualify_conversation(history, conv_id, ap, ak)
    qualification["updated_at"] = now_iso()

    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {"qualification": qualification, "tags": qualification.get("tags", [])}},
    )
    await ws_manager.broadcast(
        claims["tenant_id"],
        {"type": "conversation_update", "conversation_id": conv_id},
    )
    return {"ok": True, "qualification": qualification}


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
        # Parallelize analyze + retrieve + history-fetch — all 3 are independent and only
        # depend on inbound.text/conv_id. Saves 1-2s vs sequential.
        import asyncio
        analyze_task = analyze_message(inbound.text, inbound.channel, session, ap, ak)
        retrieve_task = retrieve(db, tenant_id, inbound.text, k=6, source_ids=agent.get("data_source_ids") or None)
        history_task = db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(20)
        (intent, structure), retrieved, history = await asyncio.gather(
            analyze_task, retrieve_task, history_task,
        )
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
    decision = decide_actions(intent, structure, agent)
    lang = _detect(inbound.text, agent.get("default_language", default_lang))

    # ===== Financial simulation hook =====
    # If the user is asking about mortgage/credit AND we can detect a price in
    # the current message or previous turn, run the simulation server-side and
    # inject it into the LLM context so Maria can speak about the actual numbers.
    finance_card = None
    # Detect intent: explicit credit keyword OR a continuation (user provided
    # credit params AND a previous AI message mentioned simulação/crédito)
    explicit_intent = detect_finance_intent(inbound.text)
    current_params = extract_credit_params(inbound.text) if not explicit_intent else {}
    is_continuation = False
    if not explicit_intent and current_params:
        for m in reversed(history[-6:]):
            if m.get("sender") == "ai" and any(
                k in (m.get("text", "") or "").lower()
                for k in ("simulação", "simulacao", "crédito", "credito",
                          "prestação", "prestacao", "entrada", "prazo")
            ):
                is_continuation = True
                break
    if explicit_intent or is_continuation:
        price = extract_price_from_text(inbound.text)
        if not price:
            for m in reversed(history):
                price = extract_price_from_text(m.get("text") or "")
                if price:
                    break
        if price and price > 10000:
            # Extract optional params (entrada%, prazo, idade) from the whole conversation
            params = {}
            all_texts = [m.get("text", "") for m in history] + [inbound.text]
            for t in reversed(all_texts):  # most recent first wins
                ext = extract_credit_params(t)
                for k, v in ext.items():
                    if k not in params:
                        params[k] = v
            try:
                comp = calcular_comparacao(price, **params)
                sim = comp["primary"]
                alt = comp["alternative"]
                # Build summary of what params were used vs defaulted
                params_used = []
                params_used.append(f"entrada {sim['entrada_pct']:.0f}% ({sim['entrada']:.0f}€)")
                params_used.append(f"prazo {sim['prazo_anos']} anos")
                if sim.get("idade"):
                    params_used.append(f"idade {sim['idade']} (banco aceita até {sim['prazo_max_bancario']} anos)")
                finance_card = {
                    "type": "finance_simulation",
                    "title": f"Simulação · {price:,.0f} €".replace(",", " "),
                    "prestacao_mensal": sim["prestacao_mensal"],
                    "entrada": sim["entrada"],
                    "entrada_pct": sim["entrada_pct"],
                    "montante": sim["montante_credito"],
                    "prazo_anos": sim["prazo_anos"],
                    "idade": sim.get("idade"),
                    "prazo_max_bancario": sim.get("prazo_max_bancario"),
                    "taxa_total_pct": sim["taxa_total_pct"],
                    "juros_totais": sim["juros_totais"],
                    "text": format_simulation_pt(sim),
                    # Cenário alternativo lado-a-lado
                    "alternative": {
                        "prazo_anos": alt["prazo_anos"],
                        "prestacao_mensal": alt["prestacao_mensal"],
                        "juros_totais": alt["juros_totais"],
                        "total_pago": alt["total_pago"],
                    },
                    "delta": comp["delta"],
                }
                # Hint Maria about missing data — so she asks for the NEXT piece
                missing = []
                if "entrada_pct" not in params: missing.append("entrada")
                if "prazo_anos" not in params and "idade" not in params: missing.append("prazo")
                if "idade" not in params: missing.append("idade")
                missing_hint = (
                    f" Dados ainda em falta para refinar: {', '.join(missing)}."
                    if missing else " Todos os dados recolhidos."
                )
                retrieved = (retrieved or []) + [{
                    "kind": "knowledge",
                    "text": (
                        f"SIMULAÇÃO CRÉDITO HABITAÇÃO calculada agora: "
                        f"Imóvel {sim['valor_imovel']:.0f}€, "
                        f"parâmetros usados: {', '.join(params_used)}. "
                        f"Taxa {sim['taxa_total_pct']:.2f}% (Euribor + Spread). "
                        f"PRESTAÇÃO MENSAL: {sim['prestacao_mensal']:.2f}€. "
                        f"Total pago: {sim['total_pago']:.0f}€, juros: {sim['juros_totais']:.0f}€."
                        f"{missing_hint}"
                    ),
                    "meta": {"topic": "simulacao_credito_live"},
                }]
            except Exception as e:
                logger.warning(f"finance simulation failed: {e}")

    try:
        resp = await generate_response(agent, history, intent, structure, retrieved, lang, session)
    except (LLMConfigMissing, LLMProviderError) as e:
        resp = {"reply": str(e), "cards": [], "language": lang}

    # Attach the structured finance card if computed
    if finance_card:
        resp.setdefault("cards", [])
        resp["cards"] = [finance_card] + list(resp.get("cards") or [])

    # Fire create_lead/create_ticket in the background — the user doesn't need
    # to wait for DB inserts and SMTP delivery before seeing the AI's reply.
    actions_to_run = decision.get("actions", [])

    ai_msg = {
        "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
        "sender": "ai", "sender_name": agent.get("name", "AI"),
        "text": resp["reply"], "cards": [],
        "meta": {"intent": intent, "language": lang},
        "created_at": now_iso(),
    }
    await db.messages.insert_one(ai_msg.copy())
    await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": ai_msg})

    # Optional follow-up message (two-bubble style) — with cards
    follow_up_text = resp.get("follow_up")
    last_text_for_preview = resp["reply"]
    if follow_up_text or resp.get("cards"):
        follow_msg = {
            "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
            "sender": "ai", "sender_name": agent.get("name", "AI"),
            "text": follow_up_text or "",
            "cards": resp.get("cards", []),
            "meta": {"follow_up": True, "language": lang},
            "created_at": now_iso(),
        }
        await db.messages.insert_one(follow_msg.copy())
        await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": follow_msg})
        if follow_up_text:
            last_text_for_preview = follow_up_text

    # ===== Background: execute_actions (lead/ticket creation) + CRM qualification =====
    # Both run AFTER the user sees the reply. Saves ~200-500ms (lead creation + email).
    full_history_snapshot = history + [{"sender": "ai", "text": resp["reply"]}]
    if follow_up_text:
        full_history_snapshot.append({"sender": "ai", "text": follow_up_text})

    async def _bg_actions_and_qualify(conv_id_inner: str, history_inner: list, tenant_inner: str,
                          session_inner: str, ap_inner: str, ak_inner: str,
                          actions_inner: list, agent_inner: dict, convo_inner: dict):
        try:
            # 1. Run create_lead / create_ticket actions
            action_results_inner = await execute_actions(db, tenant_inner, conv_id_inner, actions_inner)
            # 2. CRM qualification
            q = await qualify_conversation(history_inner, session_inner, ap_inner, ak_inner)
            q["updated_at"] = now_iso()
            new_tags = q.get("tags", []) or (convo_inner.get("tags") or [])
            await db.conversations.update_one(
                {"id": conv_id_inner},
                {"$set": {"qualification": q, "tags": new_tags}},
            )
            for a in action_results_inner:
                if a.get("tool") == "create_lead" and a.get("ok"):
                    await db.leads.update_one(
                        {"id": a["id"]},
                        {"$set": {"tags": new_tags, "qualification_status": q["status"]}},
                    )
                    # Recompute deterministic 0-100 lead score now that we have
                    # the full history + qualification snapshot
                    try:
                        await _recompute_lead_score(a["id"])
                    except Exception as e:
                        logger.warning(f"lead score failed: {e}")
                    await _notify_new_lead(tenant_inner, a["id"], agent_inner)
            await ws_manager.broadcast(
                tenant_inner,
                {"type": "conversation_update", "conversation_id": conv_id_inner},
            )
        except Exception as e:
            logger.warning(f"bg actions/qualify failed for conv {conv_id_inner}: {e}")

    asyncio.create_task(_bg_actions_and_qualify(
        conv_id, full_history_snapshot, tenant_id, session, ap, ak,
        actions_to_run, agent, convo,
    ))

    # Update conversation immediately (without qualification — that comes via WS later)
    conv_update = {
        "last_message": last_text_for_preview, "last_message_at": now_iso(),
        "intent": intent, "structure": structure, "agent_id": agent.get("id"),
        "status": "ai", "language": lang,
    }

    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": conv_update, "$inc": {"unread": 1}},
    )

    return {
        "conversation_id": conv_id,
        "reply": resp["reply"],
        "follow_up": resp.get("follow_up"),
        "cards": resp.get("cards", []),
        "intent": intent, "structure": structure,
        "actions": [], "language": lang,
    }


@api.post("/webchat/{tenant_id}/book-visit")
async def webchat_book_visit(tenant_id: str, payload: dict = Body(...)):
    """Public endpoint — visitor books a property viewing from a card.
    Creates a lead with tag 'visita-marcada' + the property/visit details in meta.
    Returns: {ok, lead_id, message_pt}."""
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")

    name  = (payload.get("name")  or "").strip()[:120]
    email = (payload.get("email") or "").strip()[:240]
    phone = (payload.get("phone") or "").strip()[:60]
    date  = (payload.get("date")  or "").strip()[:60]
    time_ = (payload.get("time")  or "").strip()[:30]
    property_title = (payload.get("property_title") or "").strip()[:200]
    property_link  = (payload.get("property_link")  or "").strip()[:600]
    external_user_id = (payload.get("external_user_id") or "").strip()[:120]
    agent_id = payload.get("agent_id")
    notes = (payload.get("notes") or "").strip()[:500]

    if not name or not email:
        raise HTTPException(400, "Nome e email são obrigatórios")
    if not date:
        raise HTTPException(400, "Data da visita é obrigatória")

    # Find associated conversation (if any)
    convo = None
    if external_user_id:
        convo = await db.conversations.find_one(
            {"tenant_id": tenant_id, "external_user_id": external_user_id,
             "status": {"$ne": "closed"}}, {"_id": 0, "id": 1},
        )

    lead_id = new_id()
    lead_doc = {
        "id": lead_id,
        "tenant_id": tenant_id,
        "name": name,
        "email": email,
        "phone": phone or None,
        "company": None,
        "source": "webchat-visit",
        "stage": "qualified",
        "score": 85,  # Strong intent — booked a viewing
        "score_tier": "quente",
        "score_signals": ["Visita marcada", "Nome partilhado", "Email partilhado",
                          "Telefone partilhado" if phone else None],
        "tags": ["visita-marcada"] + (["imobiliária"] if property_title else []),
        "notes": (
            f"📅 Visita marcada para {date}{' às ' + time_ if time_ else ''}\n"
            f"🏠 Imóvel: {property_title or 'sem referência'}\n"
            f"{('🔗 ' + property_link) if property_link else ''}\n"
            f"{notes}"
        ).strip(),
        "agent_id": agent_id,
        "conversation_id": (convo or {}).get("id"),
        "meta": {
            "visit_date": date,
            "visit_time": time_,
            "property_title": property_title,
            "property_link": property_link,
        },
        "created_at": now_iso(),
    }
    await db.leads.insert_one(lead_doc.copy())

    # Inject a message into the conversation (visible in Inbox)
    if convo:
        sys_msg = {
            "id": new_id(), "tenant_id": tenant_id, "conversation_id": convo["id"],
            "sender": "ai", "sender_name": "Sistema",
            "text": (
                f"✅ Visita marcada para {date}"
                f"{' às ' + time_ if time_ else ''} — {property_title or 'imóvel selecionado'}. "
                f"Cliente: {name} ({email})."
            ),
            "cards": [],
            "meta": {"event": "visit_booked", "lead_id": lead_id},
            "created_at": now_iso(),
        }
        await db.messages.insert_one(sys_msg.copy())
        await db.conversations.update_one(
            {"id": convo["id"]},
            {"$set": {"last_message": sys_msg["text"][:140], "last_message_at": now_iso()},
             "$addToSet": {"tags": "visita-marcada"}},
        )
        await ws_manager.broadcast(tenant_id,
            {"type": "message", "conversation_id": convo["id"], "message": sys_msg})

    # Notify owner via email (best-effort, non-blocking)
    if agent_id:
        agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
        if agent:
            try:
                await _notify_new_lead(tenant_id, lead_id, agent)
            except Exception as e:
                logger.warning(f"notify visit lead failed: {e}")

    return {
        "ok": True,
        "lead_id": lead_id,
        "message_pt": (
            f"✨ Visita agendada para {date}{' às ' + time_ if time_ else ''}. "
            f"Entraremos em contacto em {email} para confirmar."
        ),
    }


@api.post("/webchat/{tenant_id}/message")
async def webchat_inbound(tenant_id: str, inbound: InboundMessage):
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")
    inbound.channel = "webchat"
    return await _process_inbound(tenant_id, inbound, agent_id=inbound.agent_id)


@api.post("/webchat/{tenant_id}/stream")
async def webchat_stream(tenant_id: str, inbound: InboundMessage):
    """SSE streaming endpoint — same contract as /webchat/{tid}/message but
    pushes the reply tokens as they arrive from the LLM. Drops perceived latency
    from ~4s to ~400ms (time to first token).

    Stream events (one JSON per `data:` line):
      {"type": "ready", "conversation_id": str}      — sent immediately
      {"type": "chunk", "text": str}                 — reply text deltas (progressive)
      {"type": "done",  "reply": str, "follow_up": str|None, "cards": list, "conversation_id": str}
      {"type": "error", "error": str}                — on failure
    """
    import json as _json
    from ai.orchestrator import generate_response_stream
    from ai.analyze import analyze_message
    from ai.retrieval import retrieve
    from fastapi.responses import StreamingResponse

    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant não encontrado")
    inbound.channel = "webchat"
    default_lang = tenant.get("default_language", "pt")

    # Find / create conversation (same logic as _process_inbound, but inline so we
    # can stream while writing to DB in the background).
    convo = await db.conversations.find_one(
        {"tenant_id": tenant_id, "channel": "webchat",
         "external_user_id": inbound.external_user_id,
         "status": {"$ne": "closed"}}, {"_id": 0})
    if not convo:
        convo = {
            "id": new_id(), "tenant_id": tenant_id,
            "channel": "webchat", "external_user_id": inbound.external_user_id,
            "contact_name": inbound.contact_name or inbound.external_user_id,
            "agent_id": inbound.agent_id, "status": "open",
            "tags": [], "messages_count": 0,
            "last_message": inbound.text, "last_message_at": now_iso(),
            "created_at": now_iso(),
        }
        await db.conversations.insert_one(convo.copy())
    conv_id = convo["id"]
    agent_id = inbound.agent_id or convo.get("agent_id")
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": tenant_id}, {"_id": 0}) if agent_id else None
    if not agent:
        async def _err_no_agent():
            yield f"data: {_json.dumps({'type':'error','error':'Agente não encontrado'})}\n\n"
        return StreamingResponse(_err_no_agent(), media_type="text/event-stream")

    ok, err = _agent_is_configured(agent)
    if not ok:
        async def _err_cfg():
            yield f"data: {_json.dumps({'type':'error','error':err})}\n\n"
        return StreamingResponse(_err_cfg(), media_type="text/event-stream")

    user_msg = {
        "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
        "sender": "user", "sender_name": inbound.contact_name or "Cliente",
        "text": inbound.text, "cards": [], "meta": {"channel": "webchat"},
        "created_at": now_iso(),
    }
    await db.messages.insert_one(user_msg.copy())
    await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": user_msg})

    session = f"conv-{conv_id}"
    ap, ak = agent.get("api_provider", "openai"), agent.get("api_key", "")

    async def event_gen():
        # Send ready event immediately so the UI can hide typing indicator on first token
        yield f"data: {_json.dumps({'type':'ready','conversation_id':conv_id})}\n\n"
        try:
            analyze_task = analyze_message(inbound.text, "webchat", session, ap, ak)
            retrieve_task = retrieve(db, tenant_id, inbound.text, k=6, source_ids=agent.get("data_source_ids") or None)
            history_task = db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(20)
            (intent, structure), retrieved, history = await asyncio.gather(
                analyze_task, retrieve_task, history_task,
            )
            decision = decide_actions(intent, structure, agent)
            lang = _detect(inbound.text, agent.get("default_language", default_lang))

            full_reply = ""; full_follow = None; full_cards = []
            async for evt in generate_response_stream(agent, history, intent, structure, retrieved, lang, session):
                if evt["type"] == "chunk":
                    yield f"data: {_json.dumps({'type':'chunk','text':evt['text']})}\n\n"
                elif evt["type"] == "done":
                    full_reply = evt.get("reply", "")
                    full_follow = evt.get("follow_up")
                    full_cards = evt.get("cards", [])
                    yield f"data: {_json.dumps({'type':'done','reply':full_reply,'follow_up':full_follow,'cards':full_cards,'conversation_id':conv_id})}\n\n"

            # Persist AI message (after stream completes)
            ai_msg = {
                "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
                "sender": "ai", "sender_name": agent.get("name", "AI"),
                "text": full_reply, "cards": full_cards,
                "meta": {"intent": intent, "language": lang, "streamed": True},
                "created_at": now_iso(),
            }
            await db.messages.insert_one(ai_msg.copy())
            await db.conversations.update_one(
                {"id": conv_id},
                {"$set": {"last_message": full_reply, "last_message_at": now_iso()},
                 "$inc": {"messages_count": 2}},
            )
            await ws_manager.broadcast(tenant_id, {"type": "message", "conversation_id": conv_id, "message": ai_msg})

            # Background: actions + CRM qualification (matches non-streaming flow)
            full_history_snapshot = history + [{"sender": "user", "text": inbound.text},
                                               {"sender": "ai", "text": full_reply}]
            if full_follow:
                full_history_snapshot.append({"sender": "ai", "text": full_follow})

            async def _bg():
                try:
                    action_results = await execute_actions(db, tenant_id, conv_id, decision.get("actions", []))
                    q = await qualify_conversation(full_history_snapshot, session, ap, ak)
                    q["updated_at"] = now_iso()
                    await db.conversations.update_one(
                        {"id": conv_id},
                        {"$set": {"qualification": q, "tags": q.get("tags", [])}},
                    )
                    for a in action_results:
                        if a.get("tool") == "create_lead" and a.get("ok"):
                            await db.leads.update_one(
                                {"id": a["id"]},
                                {"$set": {"tags": q.get("tags", []), "qualification_status": q["status"]}},
                            )
                            await _notify_new_lead(tenant_id, a["id"], agent)
                    await ws_manager.broadcast(tenant_id, {"type": "conversation_update", "conversation_id": conv_id})
                except Exception as e:
                    logger.warning(f"bg stream actions failed: {e}")
            asyncio.create_task(_bg())

        except Exception as e:
            logger.exception(f"webchat_stream failed: {e}")
            yield f"data: {_json.dumps({'type':'error','error':str(e)[:200]})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # disables nginx proxy buffering
            "Connection": "keep-alive",
        },
    )


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
            "theme": {},
        }
    return {
        "agent_id": agent["id"], "tenant_name": tenant.get("name"),
        "name": agent.get("name", "Assistente"),
        "avatar_url": agent.get("avatar_url", ""),
        "welcome_message": agent.get("welcome_message") or "Olá! Como posso ajudar?",
        "icebreakers": agent.get("icebreakers") or [],
        "language": agent.get("default_language", "pt"),
        "theme": agent.get("theme") or {},
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


@api.post("/public/credit-simulate")
async def public_credit_simulate(body: dict):
    """Simulador de crédito habitação — fórmula Euribor 12m + spread médio PT 2025/2026.
    Cálculo indicativo apenas, não vinculativo."""
    try:
        price = float(body.get("property_value") or 0)
        down = float(body.get("down_payment") or 0)
        years = int(body.get("years") or 30)
    except (ValueError, TypeError):
        raise HTTPException(400, "Valores inválidos")

    if price <= 0 or down < 0 or years <= 0 or years > 40:
        raise HTTPException(400, "Valores fora de intervalo")
    if down >= price:
        raise HTTPException(400, "Entrada igual ou superior ao valor do imóvel")

    loan = price - down
    annual_rate = 0.035  # Euribor 12m ~2.5% + spread ~1%
    r = annual_rate / 12
    n = years * 12
    # Fórmula francesa (amortização constante)
    monthly = loan * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    total_paid = monthly * n
    total_interest = total_paid - loan
    ltv = round(loan / price * 100, 1)

    return {
        "ok": True,
        "loan_amount": round(loan, 2),
        "monthly_payment": round(monthly, 2),
        "annual_rate": annual_rate,
        "years": years,
        "total_paid": round(total_paid, 2),
        "total_interest": round(total_interest, 2),
        "ltv_percent": ltv,
        "disclaimer": "Valores indicativos. Euribor 12m + spread médio 2026. Consulte um consultor para simulação oficial.",
    }


# ======================== EMBEDDABLE WIDGET ========================
_WIDGET_PATH = ROOT_DIR / "widget.html"


def _load_widget() -> str:
    try:
        return _WIDGET_PATH.read_text(encoding="utf-8")
    except Exception:
        return "<html><body>Widget not found</body></html>"


@api.get("/widget/{tenant_id}", response_class=HTMLResponse)
async def widget_api(tenant_id: str):
    # Headers explícitos para permitir embed iframe cross-origin
    return HTMLResponse(
        _load_widget(),
        headers={
            "Access-Control-Allow-Origin": "*",
            "Content-Security-Policy": "frame-ancestors *",
            # Override any default DENY
            "X-Frame-Options": "ALLOWALL",
            "Cache-Control": "public, max-age=300",
        },
    )


_WIDGET_JS_PATH = ROOT_DIR / "widget.js"


@api.get("/widget.js")
async def widget_js_api(request: Request):
    from fastapi.responses import Response
    try:
        content = _WIDGET_JS_PATH.read_text(encoding="utf-8")
    except Exception:
        content = "/* widget.js not found */"

    # Inject the absolute backend origin so the iframe URL is bullet-proof against
    # third-party CDNs (LiteSpeed, Cloudflare, WP plugins) that may rewrite <script src>
    # as a relative path. This guarantees the chat iframe always loads from the
    # backend domain and never from the host site.
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    proto = request.headers.get("x-forwarded-proto") or ("https" if request.url.scheme == "https" else "http")
    if host:
        backend_origin = f"{proto}://{host}"
        content = content.replace("__CP_ORIGIN__", backend_origin)

    return Response(content=content, media_type="application/javascript",
                    headers={"Cache-Control": "public, max-age=60",
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
    """Public demo page — clean, professional, ready to share with clients.
    Loads the agent's actual config (name, avatar, theme, role) and embeds the live widget."""
    # Derive public URL from forwarded headers — works in any deployment
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost"
    proto = request.headers.get("x-forwarded-proto") or ("https" if request.url.scheme == "https" else "http")
    backend = f"{proto}://{host}"

    # Fetch the agent + tenant for personalisation (graceful fallback)
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": tenant_id}, {"_id": 0}) or {}
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0}) or {}

    name = agent.get("name") or "Assistente IA"
    role = agent.get("role") or "Assistente digital"
    avatar = agent.get("avatar_url") or ""
    welcome = agent.get("welcome_message") or "Olá! Como posso ajudar hoje?"
    goal = agent.get("goal") or "Apoiar clientes em tempo real, qualificar pedidos e encaminhar para a equipa."
    tenant_name = tenant.get("name") or "Consenso"

    theme = agent.get("theme") or {}
    primary = theme.get("primary") or "#0069FE"
    primary_dark = theme.get("primary_dark") or "#003F99"
    primary_soft = theme.get("primary_soft") or "#EAF2FF"
    bot_color = theme.get("bot") or primary

    # Capabilities derived from tools + sensible defaults
    tool_keys = {(t.get("key") if isinstance(t, dict) else t) for t in (agent.get("tools") or [])}
    has_lead = "create_lead" in tool_keys
    has_ticket = "create_ticket" in tool_keys

    capabilities = [
        ("💬", "Atendimento natural 24/7",
         "Responde a qualquer hora em linguagem humana, sem guiões rígidos."),
        ("🎯", "Qualifica e organiza pedidos" if has_lead else "Compreende a intenção do cliente",
         "Capta nome, email e contexto naturalmente, pronto para a equipa dar seguimento."
         if has_lead else "Identifica o que o cliente procura e adapta a resposta ao contexto."),
        ("🌍", "Multilingue automático",
         "Detecta o idioma e responde em PT, EN, ES, FR, IT, DE — sem configuração extra."),
        ("⚡", "Respostas em segundos",
         "Não há espera nem formulários. O cliente fala, o agente responde."),
    ]
    if has_ticket:
        capabilities.append((
            "🎫", "Cria tickets de apoio",
            "Quando o pedido exige um humano, cria automaticamente um ticket com o histórico."
        ))

    cap_html = "".join(
        f'<div class="cap"><div class="cap-ic">{ic}</div>'
        f'<div><h3>{t}</h3><p>{d}</p></div></div>'
        for ic, t, d in capabilities
    )

    avatar_html = (
        f'<img src="{avatar}" alt="{name}" />'
        if avatar
        else f'<span>{name[:2].upper()}</span>'
    )

    html = f"""<!doctype html>
<html lang="pt">
<head>
<meta charset="utf-8">
<title>{name} · Demonstração ao vivo</title>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="description" content="{role} · {tenant_name}. Demonstração funcional do agente IA.">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0}}
body{{font-family:Inter,system-ui,-apple-system,sans-serif;color:#0B1324;
background:#FAFBFC;line-height:1.55;-webkit-font-smoothing:antialiased}}

/* Brand variables (agent-driven) */
:root{{
  --brand:{primary};
  --brand-dark:{primary_dark};
  --brand-soft:{primary_soft};
  --bot:{bot_color};
}}

/* Top bar */
.topbar{{padding:18px 32px;display:flex;align-items:center;justify-content:space-between;
border-bottom:1px solid #EEF1F5;background:#fff;position:sticky;top:0;z-index:10;backdrop-filter:saturate(180%) blur(8px)}}
.topbar .brand{{font-weight:700;letter-spacing:-.01em;color:#0B1324;text-decoration:none;font-size:15px}}
.topbar .brand span{{color:var(--brand)}}
.topbar .right{{font-size:13px;color:#5B6B82}}
.topbar .right a{{color:var(--brand);font-weight:600;text-decoration:none}}

/* Hero */
.hero{{padding:80px 24px 60px;text-align:center;
background:radial-gradient(ellipse at 50% 0%,var(--brand-soft) 0%,transparent 60%)}}
.hero-inner{{max-width:780px;margin:0 auto}}
.av{{width:96px;height:96px;border-radius:50%;margin:0 auto 24px;
background:linear-gradient(135deg,var(--brand) 0%,var(--brand-dark) 100%);
display:flex;align-items:center;justify-content:center;color:#fff;
font-weight:700;font-size:32px;overflow:hidden;
box-shadow:0 12px 40px -8px rgba(11,19,36,.18),0 0 0 8px rgba(255,255,255,.7)}}
.av img{{width:100%;height:100%;object-fit:cover}}
.online{{display:inline-flex;align-items:center;gap:6px;font-size:12px;
font-weight:600;color:#0F8A4D;background:#E6FAEE;padding:5px 11px;
border-radius:999px;margin-bottom:18px}}
.online::before{{content:"";width:7px;height:7px;background:#0F8A4D;
border-radius:50%;box-shadow:0 0 0 0 rgba(15,138,77,.6);animation:pulse 1.6s infinite}}
@keyframes pulse{{0%{{box-shadow:0 0 0 0 rgba(15,138,77,.5)}}70%{{box-shadow:0 0 0 8px rgba(15,138,77,0)}}100%{{box-shadow:0 0 0 0 rgba(15,138,77,0)}}}}
h1{{font-size:48px;font-weight:800;letter-spacing:-.025em;margin:0 0 14px;line-height:1.1}}
.hero p.role{{font-size:18px;color:#3D4A63;margin:0 0 6px;font-weight:500}}
.hero p.welcome{{font-size:17px;color:#5B6B82;max-width:560px;margin:14px auto 0}}

/* Sections */
section{{padding:64px 24px}}
.container{{max-width:1080px;margin:0 auto}}
h2{{font-size:30px;font-weight:700;letter-spacing:-.02em;margin:0 0 12px;text-align:center}}
.sub{{font-size:15px;color:#5B6B82;text-align:center;margin:0 auto 44px;max-width:600px}}

/* What it does — intro card */
.intro{{background:#fff;border:1px solid #EEF1F5;border-radius:20px;
padding:36px;display:grid;grid-template-columns:auto 1fr;gap:24px;align-items:start;
box-shadow:0 2px 8px rgba(11,19,36,.03)}}
.intro-ic{{width:52px;height:52px;border-radius:14px;background:var(--brand-soft);
color:var(--brand);display:flex;align-items:center;justify-content:center;font-size:24px;flex-shrink:0}}
.intro h3{{margin:0 0 6px;font-size:18px;font-weight:700}}
.intro p{{margin:0;color:#3D4A63;font-size:15px}}
@media(max-width:600px){{.intro{{grid-template-columns:1fr;text-align:center}}.intro-ic{{margin:0 auto}}}}

/* Capabilities */
.caps{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;margin-top:8px}}
@media(max-width:720px){{.caps{{grid-template-columns:1fr}}}}
.cap{{background:#fff;border:1px solid #EEF1F5;border-radius:16px;padding:24px;
display:flex;gap:16px;align-items:flex-start;transition:all .2s}}
.cap:hover{{transform:translateY(-2px);box-shadow:0 12px 24px -8px rgba(11,19,36,.08);
border-color:var(--brand-soft)}}
.cap-ic{{font-size:28px;flex-shrink:0;width:48px;height:48px;background:var(--brand-soft);
border-radius:12px;display:flex;align-items:center;justify-content:center}}
.cap h3{{margin:0 0 4px;font-size:16px;font-weight:700}}
.cap p{{margin:0;color:#5B6B82;font-size:14px}}

/* Try it */
.tryit{{background:linear-gradient(135deg,var(--brand) 0%,var(--brand-dark) 100%);
border-radius:24px;padding:60px 32px;text-align:center;color:#fff;position:relative;overflow:hidden}}
.tryit::after{{content:"";position:absolute;inset:0;background:radial-gradient(circle at 80% 20%,rgba(255,255,255,.12) 1px,transparent 1px);background-size:32px 32px;pointer-events:none}}
.tryit h2{{color:#fff}}
.tryit .sub{{color:rgba(255,255,255,.85)}}
.tryit-cta{{position:relative;display:inline-flex;align-items:center;gap:8px;
background:#fff;color:var(--brand);font-weight:700;font-size:15px;
padding:14px 26px;border-radius:14px;cursor:pointer;border:0;
box-shadow:0 8px 24px -4px rgba(0,0,0,.2);transition:all .15s}}
.tryit-cta:hover{{transform:translateY(-1px);box-shadow:0 12px 28px -4px rgba(0,0,0,.25)}}

/* Value */
.value{{display:grid;grid-template-columns:repeat(4,1fr);gap:24px;margin-top:8px}}
@media(max-width:720px){{.value{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:420px){{.value{{grid-template-columns:1fr}}}}
.metric{{text-align:center;padding:28px 16px;background:#fff;border-radius:16px;border:1px solid #EEF1F5}}
.metric .num{{font-size:32px;font-weight:800;color:var(--brand);letter-spacing:-.02em;line-height:1}}
.metric .lbl{{font-size:13px;color:#5B6B82;margin-top:8px;font-weight:500}}

/* Footer */
footer{{padding:40px 24px;text-align:center;color:#9AA6B8;font-size:13px;border-top:1px solid #EEF1F5;background:#fff}}
footer a{{color:var(--brand);text-decoration:none;font-weight:600}}

/* Floating "try chat" bubble hint (only on first load) */
.hint{{position:fixed;bottom:96px;right:24px;background:#0B1324;color:#fff;
padding:10px 14px;border-radius:12px;font-size:13px;font-weight:500;
animation:slideIn .4s ease,fadeOut .4s ease 6s forwards;z-index:50;
box-shadow:0 12px 32px -4px rgba(0,0,0,.25)}}
.hint::after{{content:"";position:absolute;bottom:-6px;right:22px;
width:0;height:0;border:7px solid transparent;border-top-color:#0B1324;border-bottom:0}}
@keyframes slideIn{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes fadeOut{{to{{opacity:0;transform:translateY(8px);visibility:hidden}}}}
</style>
</head>
<body>

<div class="topbar">
  <a class="brand" href="/">Consenso<span>+</span></a>
  <div class="right">Demonstração ao vivo · <a href="https://consenso-shop.eu" target="_blank">Falar com a equipa</a></div>
</div>

<div class="hero">
  <div class="hero-inner">
    <div class="av">{avatar_html}</div>
    <div class="online">Ativo · Online agora</div>
    <h1>{name}</h1>
    <p class="role">{role} · {tenant_name}</p>
    <p class="welcome">{welcome}</p>
  </div>
</div>

<section>
  <div class="container">
    <div class="intro">
      <div class="intro-ic">✨</div>
      <div>
        <h3>O que faz por si</h3>
        <p>{goal}</p>
      </div>
    </div>
  </div>
</section>

<section style="background:#fff;border-top:1px solid #EEF1F5;border-bottom:1px solid #EEF1F5">
  <div class="container">
    <h2>Capacidades</h2>
    <p class="sub">Tudo o que este agente pode fazer para os seus clientes — em tempo real.</p>
    <div class="caps">{cap_html}</div>
  </div>
</section>

<section>
  <div class="container">
    <h2>Resultados que entrega</h2>
    <p class="sub">Disponibilidade total, qualificação automática e zero tempo de espera.</p>
    <div class="value">
      <div class="metric"><div class="num">24/7</div><div class="lbl">Disponibilidade total</div></div>
      <div class="metric"><div class="num">&lt;5s</div><div class="lbl">Tempo de resposta</div></div>
      <div class="metric"><div class="num">6+</div><div class="lbl">Idiomas suportados</div></div>
      <div class="metric"><div class="num">0€</div><div class="lbl">Em horas extra</div></div>
    </div>
  </div>
</section>

<section>
  <div class="container">
    <div class="tryit">
      <h2>Experimente agora</h2>
      <p class="sub">Carregue no botão para abrir o chat e fale diretamente com o {name.split(' ')[0]}.</p>
      <button class="tryit-cta" onclick="window.__cp_open && window.__cp_open()">
        💬 Falar com o agente
      </button>
    </div>
  </div>
</section>

<footer>
  Powered by <a href="https://consenso-agents.com" target="_blank">Consenso+</a> · Plataforma de agentes IA para empresas
</footer>

<div class="hint">Carregue aqui para falar com o agente ↓</div>

<script src="/api/widget.js" data-tenant-id="{tenant_id}" data-agent-id="{agent_id}" defer></script>
<script>
// Expose a helper to open the widget bubble from the CTA button
window.addEventListener("load", function(){{
  setTimeout(function(){{
    window.__cp_open = function(){{
      var btn = document.getElementById("cp-launcher");
      if (btn) btn.click();
    }};
    // Auto-hide hint after 6s
    setTimeout(function(){{
      var h = document.querySelector(".hint");
      if (h) h.style.display = "none";
    }}, 6500);
  }}, 800);
}});
</script>
</body>
</html>"""
    return HTMLResponse(html, headers={"Cache-Control": "public, max-age=300"})


# ======================== EXTERNAL PROPERTY FEEDS ========================
@api.get("/agents/{agent_id}/feeds")
async def list_agent_feeds(agent_id: str, claims=Depends(current_user)):
    """Lista os feeds externos configurados num agente."""
    agent = await db.agents.find_one(
        {"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0},
    )
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    feeds = (agent.get("config") or {}).get("external_feeds") or []
    # Stats por feed
    out = []
    for f in feeds:
        key = f"external-feed:{agent_id}:{(f.get('url') or '')[:60]}"
        src = await db.data_sources.find_one({"source_key": key}, {"_id": 0})
        out.append({
            **f,
            "items": (src or {}).get("items", 0),
            "indexed_at": (src or {}).get("indexed_at"),
        })
    return {"feeds": out, "follow_up_enabled": (agent.get("config") or {}).get("follow_up_enabled", True)}


@api.put("/agents/{agent_id}/feeds")
async def set_agent_feeds(agent_id: str, payload: dict = Body(...), claims=Depends(current_user)):
    """Substitui a lista de feeds externos.
    Body: {feeds: [{type: 'csv'|'xml'|'gsheet', url, name}], follow_up_enabled?: bool}"""
    agent = await db.agents.find_one(
        {"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0},
    )
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    feeds_in = payload.get("feeds") or []
    if not isinstance(feeds_in, list):
        raise HTTPException(400, "feeds deve ser uma lista")
    feeds_clean = []
    for f in feeds_in:
        if not isinstance(f, dict) or not f.get("url"):
            continue
        ftype = (f.get("type") or "csv").lower()
        if ftype not in {"csv", "xml", "gsheet"}:
            ftype = "csv"
        feeds_clean.append({
            "type": ftype,
            "url": str(f["url"])[:1000],
            "name": str(f.get("name") or "")[:120],
        })
    update_set = {"config.external_feeds": feeds_clean, "updated_at": now_iso()}
    if "follow_up_enabled" in payload:
        update_set["config.follow_up_enabled"] = bool(payload["follow_up_enabled"])
    await db.agents.update_one({"id": agent_id}, {"$set": update_set})
    return {"ok": True, "feeds": feeds_clean}


@api.post("/agents/{agent_id}/feeds/refresh")
async def refresh_agent_feeds(agent_id: str, claims=Depends(current_user)):
    """Força refresh imediato dos feeds externos deste agente."""
    agent = await db.agents.find_one(
        {"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0},
    )
    if not agent:
        raise HTTPException(404, "Agente não encontrado")
    feeds = (agent.get("config") or {}).get("external_feeds") or []
    results = []
    for f in feeds:
        r = await property_feed_module.index_external_feed(
            db, claims["tenant_id"], agent_id, f,
        )
        results.append({"url": f.get("url"), **r})
    return {"results": results}


# ======================== FOLLOW-UP MANUAL TICK ========================
@api.post("/agents/follow-up/tick")
async def run_followup_now(claims=Depends(current_user)):
    """Endpoint manual para correr o tick de follow-up imediatamente (debug/QA)."""
    if claims.get("role") not in {"owner", "admin"}:
        raise HTTPException(403, "Sem permissão")
    stats = await follow_up_module.run_followup_tick(db)
    return {"ok": True, **stats}


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


@app.on_event("startup")
async def _startup_bootstrap():
    """Auto-provision admin user + 3 agents on a fresh production DB.
    Idempotent — does nothing if data already exists."""
    from bootstrap import bootstrap
    await bootstrap(db)


@app.on_event("startup")
async def _startup_schedulers():
    """Arranca os schedulers em background:
       - WhatsApp follow-up automático (tick cada 10 min)
       - Property feed refresh (semanal)
    Desativável via env DISABLE_SCHEDULERS=1 (útil em testes)."""
    if os.environ.get("DISABLE_SCHEDULERS") == "1":
        logger.info("Schedulers disabled via DISABLE_SCHEDULERS=1")
        return
    asyncio.create_task(follow_up_module.scheduler_loop(db, interval_seconds=600))
    asyncio.create_task(property_feed_module.scheduler_loop(db, interval_seconds=7 * 24 * 3600))
