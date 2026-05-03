"""Seed script — creates the initial admin account only.
NO demo conversations, leads, tickets or sources are created.
Idempotent: safe to re-run."""
import os
import asyncio
from datetime import datetime, timezone
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

from auth import hash_password

load_dotenv(Path(__file__).parent / ".env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


def _now():
    return datetime.now(timezone.utc).isoformat()


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    existing = await db.users.find_one({"email": "demo@consenso.plus"}, {"_id": 0})
    if existing:
        print("Conta inicial já existe.")
        return

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())

    await db.tenants.insert_one({
        "id": tenant_id, "name": "A minha empresa",
        "slug": "a-minha-empresa", "plan": "pro",
        "default_language": "pt", "created_at": _now(),
    })

    await db.users.insert_one({
        "id": user_id, "tenant_id": tenant_id,
        "email": "demo@consenso.plus", "name": "Administrador",
        "role": "owner",
        "password_hash": hash_password("demo1234"),
        "created_at": _now(),
    })

    await db.agents.insert_one({
        "id": agent_id, "tenant_id": tenant_id,
        "name": "Novo Agente",
        "avatar_url": "",
        "welcome_message": "Olá! Como posso ajudar?",
        "icebreakers": [],
        "tone": "profissional",
        "goal": "Ajudar clientes",
        "system_prompt": "És um assistente útil. Responde em Português Europeu.",
        "rules": "",
        "api_provider": "emergent", "api_key": "",
        "model_provider": "auto", "model_name": "gpt-5.1",
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
            "whatsapp": {"enabled": False, "access_token": "", "phone_number_id": "", "verify_token": ""},
            "telegram": {"enabled": False, "bot_token": ""},
        },
        "email": {"enabled": False, "host": "", "port": 587, "secure": "tls",
                  "username": "", "password": "", "from_email": "", "notify_email": ""},
        "active": True, "created_at": _now(),
    })

    print(f"Conta inicial criada ({tenant_id}).")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
