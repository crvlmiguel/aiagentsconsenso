"""Seed a demo tenant so the app shows data on first load."""
import os
import asyncio
from datetime import datetime, timezone, timedelta
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

from auth import hash_password

load_dotenv(Path(__file__).parent / ".env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _now(offset_min=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=offset_min)).isoformat()


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    existing = await db.users.find_one({"email": "demo@consenso.plus"}, {"_id": 0})
    if existing:
        print("Demo tenant already seeded.")
        return

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    await db.tenants.insert_one({
        "id": tenant_id,
        "name": "Acme Corp",
        "slug": "acme",
        "plan": "pro",
        "created_at": _now(),
    })

    await db.users.insert_one({
        "id": user_id,
        "tenant_id": tenant_id,
        "email": "demo@consenso.plus",
        "name": "Demo Owner",
        "role": "owner",
        "password_hash": hash_password("demo1234"),
        "created_at": _now(),
    })

    # Default Agent
    await db.agents.insert_one({
        "id": agent_id,
        "tenant_id": tenant_id,
        "name": "Aria — Default AI",
        "tone": "friendly yet professional",
        "goal": "Qualify leads, answer FAQs, route complex cases to humans.",
        "system_prompt": "You are Aria, the AI concierge for Acme Corp. Be concise, warm, accurate.",
        "rules": "If the user asks about pricing, collect their email. For refunds, create a support ticket. Never invent policies.",
        "model_provider": "auto",
        "model_name": "gpt-5.1",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
            {"key": "send_email", "enabled": False},
            {"key": "webhook", "enabled": False},
        ],
        "knowledge": "Acme sells a B2B analytics suite. Plans: Starter $49, Growth $149, Scale $499. Free trial: 14 days. Support hours: Mon-Fri 9-6 PT.",
        "active": True,
        "created_at": _now(),
    })

    # Integrations
    for kind, cat, name, status in [
        ("webchat", "channel", "Web Chat Widget", "connected"),
        ("whatsapp", "channel", "WhatsApp Cloud", "disconnected"),
        ("instagram", "channel", "Instagram DM", "disconnected"),
        ("telegram", "channel", "Telegram Bot", "disconnected"),
        ("messenger", "channel", "Messenger", "disconnected"),
        ("hubspot", "crm", "HubSpot", "disconnected"),
        ("pipedrive", "crm", "Pipedrive", "disconnected"),
        ("salesforce", "crm", "Salesforce", "disconnected"),
        ("webhook", "crm", "Generic Webhook", "disconnected"),
    ]:
        await db.integrations.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "kind": kind,
            "category": cat,
            "name": name,
            "status": status,
            "config": {},
            "created_at": _now(),
        })

    # Seed 3 demo conversations with messages
    demo_convos = [
        {
            "contact_name": "Sarah Chen",
            "channel": "webchat",
            "status": "ai",
            "last_message": "Can I see pricing for 50 seats?",
            "messages": [
                ("user", "Sarah Chen", "Hi! I'm evaluating your analytics suite.", -45),
                ("ai", "Aria", "Hey Sarah — happy to help. Which team size are you planning for?", -44),
                ("user", "Sarah Chen", "Can I see pricing for 50 seats?", -2),
            ],
            "intent": {"intent": "pricing", "category": "sales", "urgency": "medium", "confidence": 0.92},
            "tags": ["pricing", "enterprise"],
        },
        {
            "contact_name": "Miguel Ortiz",
            "channel": "whatsapp",
            "status": "human",
            "last_message": "Still not working after the reinstall.",
            "messages": [
                ("user", "Miguel Ortiz", "My dashboard crashes every time I open reports.", -120),
                ("ai", "Aria", "Sorry to hear that. Can you tell me which browser/version?", -118),
                ("user", "Miguel Ortiz", "Chrome 132 on macOS.", -117),
                ("human", "Demo Owner", "Hi Miguel, I'm taking over. Let's get this sorted.", -10),
                ("user", "Miguel Ortiz", "Still not working after the reinstall.", -1),
            ],
            "intent": {"intent": "support_request", "category": "technical", "urgency": "high", "confidence": 0.88},
            "tags": ["bug", "chrome"],
        },
        {
            "contact_name": "Priya Raman",
            "channel": "instagram",
            "status": "closed",
            "last_message": "Thanks! Got it.",
            "messages": [
                ("user", "Priya Raman", "Do you have a free trial?", -2880),
                ("ai", "Aria", "Yes — 14 days, no card needed. Want me to send the link?", -2879),
                ("user", "Priya Raman", "Thanks! Got it.", -2870),
            ],
            "intent": {"intent": "information", "category": "sales", "urgency": "low", "confidence": 0.95},
            "tags": ["trial"],
        },
    ]

    for c in demo_convos:
        conv_id = str(uuid.uuid4())
        await db.conversations.insert_one({
            "id": conv_id,
            "tenant_id": tenant_id,
            "channel": c["channel"],
            "external_user_id": str(uuid.uuid4()),
            "contact_name": c["contact_name"],
            "contact_avatar": None,
            "status": c["status"],
            "assigned_to": user_id if c["status"] == "human" else None,
            "agent_id": agent_id,
            "tags": c["tags"],
            "last_message": c["last_message"],
            "last_message_at": _now(c["messages"][-1][3]),
            "unread": 1 if c["status"] != "closed" else 0,
            "intent": c["intent"],
            "structure": None,
            "created_at": _now(c["messages"][0][3]),
        })
        for sender, sender_name, text, off in c["messages"]:
            await db.messages.insert_one({
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "sender": sender,
                "sender_name": sender_name,
                "text": text,
                "meta": {},
                "created_at": _now(off),
            })

    # Seed leads / tickets
    await db.leads.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "name": "Sarah Chen",
        "email": "sarah@globex.io",
        "phone": None,
        "company": "Globex",
        "source": "ai",
        "stage": "qualified",
        "score": 85,
        "notes": "50-seat eval, wants pricing and SSO.",
        "conversation_id": None,
        "created_at": _now(-30),
    })
    await db.tickets.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "subject": "Dashboard crashes on reports page",
        "description": "Chrome 132 macOS, reproducible.",
        "priority": "high",
        "status": "in_progress",
        "assigned_to": user_id,
        "conversation_id": None,
        "created_at": _now(-60),
    })

    print(f"Seeded tenant {tenant_id} | login: demo@consenso.plus / demo1234")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
