"""Production bootstrap — runs once at backend startup.

Idempotent: if the admin user + 4 agents already exist, does nothing.
On a fresh production database, this auto-creates:
- Tenant "Consenso"
- Admin user `admin@consenso-agents.com` / `100%Consenso`
- 4 agents: Abby (ABBI), Maria (Consenso), StayLocal, Tejo Sailing
- All knowledge bases / data sources for each agent

This avoids the need to ssh into production or run scripts manually.
"""
import logging
import os
import uuid
from datetime import datetime, timezone

from auth import hash_password

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASSWORD = "100%Consenso"
TENANT_NAME = "Consenso"


def _now():
    return datetime.now(timezone.utc).isoformat()


async def _ensure_admin(db) -> str:
    """Returns tenant_id of the admin (created if missing)."""
    user = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if user:
        return user["tenant_id"]

    tenant_id = str(uuid.uuid4())
    await db.tenants.insert_one({
        "id": tenant_id, "name": TENANT_NAME,
        "default_language": "pt", "created_at": _now(),
    })
    await db.users.insert_one({
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "email": ADMIN_EMAIL, "name": "Administrador",
        "password_hash": hash_password(ADMIN_PASSWORD),
        "role": "admin", "created_at": _now(),
    })
    logger.info(f"[bootstrap] created admin user + tenant '{TENANT_NAME}' ({tenant_id[:8]}…)")
    return tenant_id


async def _ensure_agent_with_kb(db, tenant_id: str, agent_def: dict, kb: list[dict]):
    """Create or update an agent with its knowledge base.
    Idempotent — only creates if no agent of that name exists in the tenant."""
    name = agent_def["name"]
    existing = await db.agents.find_one(
        {"tenant_id": tenant_id, "name": {"$regex": name.split("—")[0].strip(), "$options": "i"}},
        {"_id": 0},
    )
    if existing:
        return  # do not touch user-edited agents

    # Build data source
    source_id = str(uuid.uuid4())
    src_name = agent_def.get("kb_name", f"{name} — KB")
    await db.data_sources.insert_one({
        "id": source_id, "tenant_id": tenant_id, "name": src_name,
        "type": "knowledge_base", "url": agent_def.get("kb_url", ""),
        "items": len(kb), "chunks": len(kb),
        "indexed_at": _now(), "created_at": _now(),
    })
    for ch in kb:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id, "source_id": source_id,
            "kind": "knowledge", "title": ch["topic"], "text": ch["text"],
            "meta": {"topic": ch["topic"]}, "indexed_at": _now(),
        })

    # Build agent
    agent_id = str(uuid.uuid4())
    await db.agents.insert_one({
        "id": agent_id, "tenant_id": tenant_id,
        "name": name,
        "active": True,
        "avatar_url": agent_def.get("avatar_url", ""),
        "theme": agent_def.get("theme", {}),
        "role": agent_def.get("role", ""),
        "goal": agent_def.get("goal", ""),
        "tone": agent_def.get("tone", ""),
        "rules": agent_def.get("rules", ""),
        "system_prompt": agent_def["system_prompt"],
        "knowledge": "\n\n".join(c["text"] for c in kb),
        "default_language": "pt",
        "icebreakers": agent_def.get("icebreakers", []),
        "welcome_message": agent_def.get("welcome_message", "Olá! Como posso ajudar?"),
        "api_provider": "emergent", "api_key": "",
        "model_provider": "auto", "model_name": "gemini-2.5-flash",
        "data_source_ids": [source_id],
        "tools": [{"key": "create_lead", "enabled": True}],
        "channels": {
            "webchat": {"active": True},
            "whatsapp": {"active": False},
            "telegram": {"active": False},
            "instagram": {"active": False},
            "messenger": {"active": False},
        },
        "email_config": {},
        "config": {"max_history": 24, "lead_capture_required": True},
        "created_at": _now(), "updated_at": _now(),
    })
    logger.info(f"[bootstrap] created agent '{name}' ({agent_id[:8]}…)")


async def bootstrap(db):
    """Called once at backend startup. Idempotent — safe to re-run."""
    try:
        tenant_id = await _ensure_admin(db)

        # Lazy imports of seed defs (kept in seed_*.py for separation of concerns)
        from seed_maria import (
            SYSTEM_PROMPT as MARIA_PROMPT,
            ICEBREAKERS as MARIA_ICE,
            WELCOME_MESSAGE as MARIA_WELCOME,
            AVATAR_URL as MARIA_AVATAR,
            THEME as MARIA_THEME,
            KNOWLEDGE_CHUNKS as MARIA_KB,
        )
        from seed_staylocal import (
            SYSTEM_PROMPT as SL_PROMPT,
            ICEBREAKERS as SL_ICE,
            WELCOME_MESSAGE as SL_WELCOME,
            AVATAR_URL as SL_AVATAR,
            THEME as SL_THEME,
            KNOWLEDGE_CHUNKS as SL_KB,
        )
        from seed_tejo_sailing import (
            SYSTEM_PROMPT as TJ_PROMPT,
            ICEBREAKERS as TJ_ICE,
            WELCOME_MESSAGE as TJ_WELCOME,
            AVATAR_URL as TJ_AVATAR,
            THEME as TJ_THEME,
            KNOWLEDGE_CHUNKS as TJ_KB,
        )

        await _ensure_agent_with_kb(db, tenant_id, {
            "name": "Maria — Assistente Consenso",
            "role": "Consultora digital imobiliária — Consenso AI",
            "goal": "Explicar agentes IA para imobiliárias, demonstrar uma simulação real e converter visitantes em pedidos de demonstração.",
            "system_prompt": MARIA_PROMPT,
            "icebreakers": MARIA_ICE, "welcome_message": MARIA_WELCOME,
            "avatar_url": MARIA_AVATAR, "theme": MARIA_THEME,
            "kb_name": "Site Consenso", "kb_url": "https://consenso-shop.eu",
        }, MARIA_KB)

        await _ensure_agent_with_kb(db, tenant_id, {
            "name": "StayLocal Concierge AI",
            "role": "Concierge digital de hotel premium",
            "goal": "Explicar o conceito StayLocal, qualificar pedidos de reserva, recomendar experiências locais e converter em reservas.",
            "system_prompt": SL_PROMPT,
            "icebreakers": SL_ICE, "welcome_message": SL_WELCOME,
            "avatar_url": SL_AVATAR, "theme": SL_THEME,
            "kb_name": "Conceito StayLocal",
        }, SL_KB)

        await _ensure_agent_with_kb(db, tenant_id, {
            "name": "Tejo Sunset Sailing AI Guide",
            "role": "Concierge de luxo turístico",
            "goal": "Vender experiências de passeio de veleiro ao pôr do sol no Tejo, personalizar reservas e converter em reservas confirmadas pela equipa.",
            "system_prompt": TJ_PROMPT,
            "icebreakers": TJ_ICE, "welcome_message": TJ_WELCOME,
            "avatar_url": TJ_AVATAR, "theme": TJ_THEME,
            "kb_name": "Tejo Sunset Sailing — Experiências",
        }, TJ_KB)

        # Note: Abby (ABBI Imóveis) requires the full property catalogue — left to be
        # seeded manually via `python seed_abbi.py` if/when the ABBI tenant is needed
        # in production. The 3 self-promotion agents (Maria, StayLocal, Tejo) are
        # always provisioned automatically.
    except Exception as e:
        logger.error(f"[bootstrap] failed: {e}", exc_info=True)
