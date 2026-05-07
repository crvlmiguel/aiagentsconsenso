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
        "id": tenant_id,
        "name": TENANT_NAME,
        "slug": "consenso",
        "plan": "pro",
        "default_language": "pt",
        "created_at": _now(),
    })
    await db.users.insert_one({
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "email": ADMIN_EMAIL, "name": "Administrador",
        "password_hash": hash_password(ADMIN_PASSWORD),
        "role": "owner",
        "created_at": _now(),
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


async def _ensure_abby(db, tenant_id: str):
    """Provision Abby — ABBI Imóveis with full 9-property catalogue.
    Idempotent — does nothing if an Abby agent already exists in the tenant."""
    existing = await db.agents.find_one(
        {"tenant_id": tenant_id, "name": {"$regex": "Abby|ABBI", "$options": "i"}},
        {"_id": 0},
    )
    if existing:
        return

    # Lazy import to avoid loading the 9-property catalogue unless needed
    from seed_abbi import PROPERTIES

    agent_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())

    await db.data_sources.insert_one({
        "id": source_id, "tenant_id": tenant_id, "agent_id": agent_id,
        "name": "Catálogo ABBI Imóveis",
        "type": "website",
        "source_url": "https://abbimoveis.com/imovel/",
        "status": "ready",
        "chunks": len(PROPERTIES), "items": len(PROPERTIES),
        "indexed_at": _now(), "created_at": _now(),
    })
    for p in PROPERTIES:
        chunk_text = (
            f"{p['title']} — Referência {p['ref']}. "
            f"Tipo: {p['type']} {p['tipologia']}. "
            f"Localização: {p['location']}. "
            f"Área: {p['area']}. "
            f"{p['bedrooms']} quartos, {p['bathrooms']} WC, {p['parking']}. "
            f"Estado: {p['status']}. Preço: {p['price']}. "
            f"{p['description']} Link: {p['link']}"
        )
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "source_id": source_id, "kind": "item", "text": chunk_text,
            "meta": {
                "title": p["title"], "price": p["price"], "location": p["location"],
                "image": p["image"], "link": p["link"],
                "description": p["description"],
                "tipologia": p["tipologia"], "type": p["type"],
                "ref": p["ref"], "status": p["status"],
                "area": p["area"], "bedrooms": p["bedrooms"],
            },
            "created_at": _now(),
        })

    system_prompt = (
        "És a Abby, assistente imobiliária virtual da ABBI Imóveis (ABB Imóveis). "
        "PERSONALIDADE: profissional, comunicativa e extremamente amigável, sem ser formal ou robótica. "
        "Falas com os clientes como um colega experiente — com calor humano, proximidade e à-vontade. "
        "Ajudas clientes a descobrir imóveis do portfolio ABBI — moradias, apartamentos e empreendimentos "
        "em Lagos, Porto, Braga, Guimarães, Maia, Barcelos, Vila Nova de Famalicão. "
        "IDIOMA: detectas automaticamente o idioma do cliente e respondes SEMPRE no MESMO idioma. "
        "Português Europeu (pt-PT, NUNCA pt-BR). "
        "Os preços não estão publicados — indica 'Sob consulta' e oferece contacto com a equipa."
    )
    rules = (
        "DINÂMICA: Mensagens curtas (estilo WhatsApp). Nunca textos longos. Divide em 2 balões quando necessário. "
        "Termina com call-to-action claro com 2 opções. "
        "APRESENTAÇÃO: assim que o cliente mencione zona/tipologia, mostra IMEDIATAMENTE 2-3 cards. Não inventes imóveis. "
        "OBJETIVO: cada conversa deve obter Nome + Email + Interesse (zona+tipologia+orçamento). "
        "Recolhe dados naturalmente, NUNCA tudo de uma vez. "
        "SIMULADOR DE CRÉDITO: pede valor do imóvel + entrada. Calcula prestação a 30 anos, taxa 3.5% (Euribor 12m + spread). "
        "Prestação = empréstimo × (r×(1+r)^n) / ((1+r)^n - 1) onde r=0.035/12, n=360. "
        "Sempre VALOR INDICATIVO, e pede contacto para consultor validar. "
        "Contacto fallback: +351 253 142 000 · geral@abborges.pt"
    )

    await db.agents.insert_one({
        "id": agent_id, "tenant_id": tenant_id,
        "name": "Abby — ABBI Imóveis",
        "active": True,
        "avatar_url": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=200&h=200&fit=crop",
        "theme": {
            "primary": "#c9a84d", "primary_dark": "#a88838",
            "primary_soft": "#FAF4E2", "primary_border": "#E8D8A8",
            "bot": "#4e7bfa",
        },
        "welcome_message": "Olá! Como posso ajudar hoje?",
        "icebreakers": [
            "🏠 Comprar e simular prestação",
            "🔑 Procurar casa para arrendar",
            "📈 Imóveis para investimento",
            "📑 Que documentos preciso?",
        ],
        "tone": "profissional, comunicativo, extremamente amigável, conversacional como uma pessoa real",
        "goal": "Apresentar imóveis do catálogo ABBI, qualificar interesse e capturar leads para a equipa comercial.",
        "system_prompt": system_prompt, "rules": rules,
        "api_provider": "emergent", "api_key": "",
        "model_provider": "auto", "model_name": "gemini-2.5-flash",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
        ],
        "knowledge": (
            "A ABBI Imóveis (ABB Imóveis) é uma promotora e mediadora imobiliária com "
            "empreendimentos em Lagos (Algarve), Porto, Braga, Guimarães, Maia, Barcelos e "
            "Vila Nova de Famalicão. Catálogo atual: 9 empreendimentos entre moradias V3/V4 e "
            "apartamentos T1/T2/T3/T4. Contacto: +351 253 142 000 · geral@abborges.pt. "
            "Site: https://abbimoveis.com"
        ),
        "data_source_ids": [source_id], "default_language": "pt",
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
    logger.info(f"[bootstrap] created agent 'Abby — ABBI Imóveis' with {len(PROPERTIES)} properties")


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

        # Note: Abby (ABBI Imóveis) — full 9-property catalogue auto-provisioned.
        await _ensure_abby(db, tenant_id)
    except Exception as e:
        logger.error(f"[bootstrap] failed: {e}", exc_info=True)
