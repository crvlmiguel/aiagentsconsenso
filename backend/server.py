"""Consenso Plus — AI Business Operating System (multi-tenant SaaS backend)."""
import os
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Query
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from models import (
    Tenant, User, RegisterInput, LoginInput, AuthResponse,
    Agent, AgentInput,
    Integration,
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

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="Consenso Plus API")
api = APIRouter(prefix="/api")


# ======================== AUTH ========================
@api.post("/auth/register", response_model=AuthResponse)
async def register(inp: RegisterInput):
    existing = await db.users.find_one({"email": inp.email}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Email already registered")

    tenant_id = new_id()
    slug = inp.company_name.lower().replace(" ", "-")[:40]
    tenant_doc = {
        "id": tenant_id, "name": inp.company_name, "slug": slug,
        "plan": "pro", "created_at": now_iso(),
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

    # Default AI agent
    await db.agents.insert_one({
        "id": new_id(), "tenant_id": tenant_id,
        "name": "Default AI Agent", "tone": "professional",
        "goal": "Help customers and qualify leads",
        "system_prompt": f"You are the AI assistant for {inp.company_name}. Be helpful, concise, accurate.",
        "rules": "", "model_provider": "auto", "model_name": "gpt-5.1",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
        ],
        "knowledge": "", "active": True, "created_at": now_iso(),
    })

    # Seed webchat integration (always connected)
    await db.integrations.insert_one({
        "id": new_id(), "tenant_id": tenant_id,
        "kind": "webchat", "category": "channel",
        "name": "Web Chat Widget", "status": "connected",
        "config": {}, "created_at": now_iso(),
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
        raise HTTPException(401, "Invalid credentials")
    tenant = await db.tenants.find_one({"id": user["tenant_id"]}, {"_id": 0})
    token = create_token(user["id"], user["tenant_id"], user.get("role", "owner"))
    user_clean = {k: v for k, v in user.items() if k != "password_hash"}
    return AuthResponse(token=token, user=User(**user_clean), tenant=Tenant(**tenant))


@api.get("/auth/me")
async def me(claims=Depends(current_user)):
    user = await db.users.find_one({"id": claims["sub"]}, {"_id": 0, "password_hash": 0})
    tenant = await db.tenants.find_one({"id": claims["tenant_id"]}, {"_id": 0})
    if not user or not tenant:
        raise HTTPException(404, "User/tenant not found")
    return {"user": user, "tenant": tenant}


# ======================== DASHBOARD ========================
@api.get("/dashboard/stats")
async def dashboard_stats(claims=Depends(current_user)):
    t = claims["tenant_id"]
    convos = await db.conversations.count_documents({"tenant_id": t})
    open_convos = await db.conversations.count_documents({"tenant_id": t, "status": {"$in": ["ai", "human", "open"]}})
    leads = await db.leads.count_documents({"tenant_id": t})
    tickets_open = await db.tickets.count_documents({"tenant_id": t, "status": {"$in": ["open", "in_progress"]}})
    messages = await db.messages.count_documents({"tenant_id": t})

    # per-channel breakdown
    pipeline = [
        {"$match": {"tenant_id": t}},
        {"$group": {"_id": "$channel", "count": {"$sum": 1}}},
    ]
    by_channel = [{"channel": d["_id"], "count": d["count"]} async for d in db.conversations.aggregate(pipeline)]

    # leads by stage
    pipeline2 = [
        {"$match": {"tenant_id": t}},
        {"$group": {"_id": "$stage", "count": {"$sum": 1}}},
    ]
    by_stage = [{"stage": d["_id"], "count": d["count"]} async for d in db.leads.aggregate(pipeline2)]

    return {
        "conversations": convos,
        "open_conversations": open_convos,
        "leads": leads,
        "open_tickets": tickets_open,
        "messages": messages,
        "by_channel": by_channel,
        "by_stage": by_stage,
    }


# ======================== AGENTS ========================
@api.get("/agents")
async def list_agents(claims=Depends(current_user)):
    items = await db.agents.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).to_list(200)
    return items


@api.post("/agents")
async def create_agent(inp: AgentInput, claims=Depends(current_user)):
    agent = Agent(tenant_id=claims["tenant_id"], **inp.model_dump())
    await db.agents.insert_one(agent.model_dump())
    return agent.model_dump()


@api.put("/agents/{agent_id}")
async def update_agent(agent_id: str, inp: AgentInput, claims=Depends(current_user)):
    update = inp.model_dump()
    res = await db.agents.update_one(
        {"id": agent_id, "tenant_id": claims["tenant_id"]},
        {"$set": update},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Agent not found")
    doc = await db.agents.find_one({"id": agent_id}, {"_id": 0})
    return doc


@api.delete("/agents/{agent_id}")
async def delete_agent(agent_id: str, claims=Depends(current_user)):
    await db.agents.delete_one({"id": agent_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


@api.post("/agents/{agent_id}/test")
async def test_agent(agent_id: str, inp: SendMessageInput, claims=Depends(current_user)):
    agent = await db.agents.find_one({"id": agent_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not agent:
        raise HTTPException(404, "Agent not found")
    session = f"test-{agent_id}"
    intent = await classify_intent(inp.text, session)
    structure = await structure_message(inp.text, "webchat", session)
    decision = decide_actions(intent, structure, agent)
    reply = await generate_response(agent, [{"sender": "user", "text": inp.text}], intent, structure, session)
    return {"intent": intent, "structure": structure, "decision": decision, "reply": reply}


# ======================== CONVERSATIONS ========================
@api.get("/conversations")
async def list_conversations(
    claims=Depends(current_user),
    channel: Optional[str] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
):
    query: dict = {"tenant_id": claims["tenant_id"]}
    if channel and channel != "all":
        query["channel"] = channel
    if status and status != "all":
        query["status"] = status
    if q:
        query["contact_name"] = {"$regex": q, "$options": "i"}
    items = await db.conversations.find(query, {"_id": 0}).sort("last_message_at", -1).to_list(200)
    return items


@api.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str, claims=Depends(current_user)):
    convo = await db.conversations.find_one({"id": conv_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not convo:
        raise HTTPException(404, "Not found")
    messages = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    # mark as read
    await db.conversations.update_one({"id": conv_id}, {"$set": {"unread": 0}})
    return {"conversation": convo, "messages": messages}


@api.post("/conversations/{conv_id}/takeover")
async def takeover(conv_id: str, claims=Depends(current_user)):
    res = await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$set": {"status": "human", "assigned_to": claims["sub"]}},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return {"ok": True, "status": "human"}


@api.post("/conversations/{conv_id}/release")
async def release(conv_id: str, claims=Depends(current_user)):
    await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$set": {"status": "ai", "assigned_to": None}},
    )
    return {"ok": True, "status": "ai"}


@api.post("/conversations/{conv_id}/close")
async def close_conv(conv_id: str, claims=Depends(current_user)):
    await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$set": {"status": "closed"}},
    )
    return {"ok": True, "status": "closed"}


@api.post("/conversations/{conv_id}/messages")
async def send_human_message(conv_id: str, inp: SendMessageInput, claims=Depends(current_user)):
    convo = await db.conversations.find_one({"id": conv_id, "tenant_id": claims["tenant_id"]}, {"_id": 0})
    if not convo:
        raise HTTPException(404, "Not found")
    user_doc = await db.users.find_one({"id": claims["sub"]}, {"_id": 0})
    msg = {
        "id": new_id(), "tenant_id": claims["tenant_id"], "conversation_id": conv_id,
        "sender": "human", "sender_name": user_doc.get("name", "Agent") if user_doc else "Agent",
        "text": inp.text, "meta": {}, "created_at": now_iso(),
    }
    await db.messages.insert_one(msg.copy())
    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {"last_message": inp.text, "last_message_at": now_iso(),
                  "status": "human", "assigned_to": claims["sub"]}},
    )
    return msg


@api.post("/conversations/{conv_id}/tag")
async def add_tag(conv_id: str, body: dict, claims=Depends(current_user)):
    tag = body.get("tag", "").strip().lower()
    if not tag:
        raise HTTPException(400, "tag required")
    await db.conversations.update_one(
        {"id": conv_id, "tenant_id": claims["tenant_id"]},
        {"$addToSet": {"tags": tag}},
    )
    return {"ok": True}


# ======================== INBOUND (public) ========================
async def _process_inbound(tenant_id: str, inbound: InboundMessage) -> dict:
    """Full pipeline: normalize -> classify -> structure -> orchestrate -> tools -> reply."""
    # Find or create conversation
    convo = await db.conversations.find_one(
        {"tenant_id": tenant_id, "channel": inbound.channel,
         "external_user_id": inbound.external_user_id,
         "status": {"$ne": "closed"}},
        {"_id": 0},
    )
    if not convo:
        convo = {
            "id": new_id(), "tenant_id": tenant_id,
            "channel": inbound.channel,
            "external_user_id": inbound.external_user_id,
            "contact_name": inbound.contact_name,
            "contact_avatar": None,
            "status": "ai", "assigned_to": None, "agent_id": None,
            "tags": [], "last_message": inbound.text,
            "last_message_at": now_iso(), "unread": 1,
            "intent": None, "structure": None, "created_at": now_iso(),
        }
        await db.conversations.insert_one(convo.copy())

    conv_id = convo["id"]

    # Store user message
    user_msg = {
        "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
        "sender": "user", "sender_name": inbound.contact_name,
        "text": inbound.text, "meta": {}, "created_at": now_iso(),
    }
    await db.messages.insert_one(user_msg.copy())

    # If human is in control, don't auto-reply
    if convo["status"] == "human":
        await db.conversations.update_one(
            {"id": conv_id},
            {"$set": {"last_message": inbound.text, "last_message_at": now_iso()},
             "$inc": {"unread": 1}},
        )
        return {"conversation_id": conv_id, "auto_reply": None, "handoff": True}

    # Pick an agent
    agent = await db.agents.find_one({"tenant_id": tenant_id, "active": True}, {"_id": 0})
    if not agent:
        agent = {"name": "AI", "tone": "professional", "goal": "help",
                 "system_prompt": "You are helpful.", "rules": "",
                 "model_provider": "auto", "model_name": "gpt-5.1",
                 "tools": [], "knowledge": ""}

    session = f"conv-{conv_id}"
    intent = await classify_intent(inbound.text, session)
    structure = await structure_message(inbound.text, inbound.channel, session)
    decision = decide_actions(intent, structure, agent)

    history = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(20)
    reply_text = await generate_response(agent, history, intent, structure, session)

    action_results = await execute_actions(db, tenant_id, conv_id, decision.get("actions", []))

    ai_msg = {
        "id": new_id(), "tenant_id": tenant_id, "conversation_id": conv_id,
        "sender": "ai", "sender_name": agent.get("name", "AI"),
        "text": reply_text,
        "meta": {"intent": intent, "actions": action_results},
        "created_at": now_iso(),
    }
    await db.messages.insert_one(ai_msg.copy())

    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {
            "last_message": reply_text, "last_message_at": now_iso(),
            "intent": intent, "structure": structure, "agent_id": agent.get("id"),
            "status": "ai",
        }, "$inc": {"unread": 1}},
    )

    return {
        "conversation_id": conv_id,
        "auto_reply": reply_text,
        "intent": intent,
        "structure": structure,
        "actions": action_results,
    }


@api.post("/webchat/{tenant_id}/message")
async def webchat_inbound(tenant_id: str, inbound: InboundMessage):
    """Public endpoint - used by the embeddable Web Chat widget."""
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    inbound.channel = "webchat"
    return await _process_inbound(tenant_id, inbound)


@api.post("/inbound/simulate")
async def simulate_inbound(inbound: InboundMessage, claims=Depends(current_user)):
    """Authenticated simulator for demoing any channel."""
    return await _process_inbound(claims["tenant_id"], inbound)


# ======================== LEADS ========================
@api.get("/leads")
async def list_leads(claims=Depends(current_user)):
    items = await db.leads.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


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
        raise HTTPException(404, "Not found")
    return await db.leads.find_one({"id": lead_id}, {"_id": 0})


@api.delete("/leads/{lead_id}")
async def delete_lead(lead_id: str, claims=Depends(current_user)):
    await db.leads.delete_one({"id": lead_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


# ======================== TICKETS ========================
@api.get("/tickets")
async def list_tickets(claims=Depends(current_user)):
    items = await db.tickets.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


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
        raise HTTPException(404, "Not found")
    return await db.tickets.find_one({"id": ticket_id}, {"_id": 0})


@api.delete("/tickets/{ticket_id}")
async def delete_ticket(ticket_id: str, claims=Depends(current_user)):
    await db.tickets.delete_one({"id": ticket_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


# ======================== INTEGRATIONS ========================
@api.get("/integrations")
async def list_integrations(claims=Depends(current_user)):
    items = await db.integrations.find({"tenant_id": claims["tenant_id"]}, {"_id": 0}).to_list(200)
    return items


@api.put("/integrations/{int_id}")
async def update_integration(int_id: str, body: dict, claims=Depends(current_user)):
    allowed = {k: v for k, v in body.items() if k in {"status", "config", "name"}}
    res = await db.integrations.update_one(
        {"id": int_id, "tenant_id": claims["tenant_id"]},
        {"$set": allowed},
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    return await db.integrations.find_one({"id": int_id}, {"_id": 0})


# ======================== TEAM ========================
@api.get("/team")
async def list_team(claims=Depends(current_user)):
    items = await db.users.find(
        {"tenant_id": claims["tenant_id"]},
        {"_id": 0, "password_hash": 0},
    ).to_list(200)
    return items


@api.post("/team/invite")
async def invite_member(inv: TeamInvite, claims=Depends(current_user)):
    existing = await db.users.find_one({"email": inv.email}, {"_id": 0})
    if existing:
        raise HTTPException(409, "Email already exists")
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
        raise HTTPException(400, "Cannot remove yourself")
    await db.users.delete_one({"id": user_id, "tenant_id": claims["tenant_id"]})
    return {"ok": True}


# ======================== PLATFORM ADMIN ========================
@api.get("/admin/tenants")
async def list_all_tenants(claims=Depends(current_user)):
    if claims.get("role") != "platform_admin" and claims.get("role") != "owner":
        # allow owners to see their own tenant stats (read-only self view)
        tenant = await db.tenants.find_one({"id": claims["tenant_id"]}, {"_id": 0})
        return [tenant] if tenant else []
    tenants = await db.tenants.find({}, {"_id": 0}).to_list(500)
    result = []
    for t in tenants:
        users = await db.users.count_documents({"tenant_id": t["id"]})
        convos = await db.conversations.count_documents({"tenant_id": t["id"]})
        leads = await db.leads.count_documents({"tenant_id": t["id"]})
        result.append({**t, "users": users, "conversations": convos, "leads": leads})
    return result


# ======================== ROOT ========================
@api.get("/")
async def root():
    return {"name": "Consenso Plus", "version": "1.0.0", "status": "ok"}


app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
logger = logging.getLogger("consenso")


@app.on_event("shutdown")
async def _shutdown():
    client.close()
