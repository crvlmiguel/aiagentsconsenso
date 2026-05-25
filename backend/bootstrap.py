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
from brand import CONSENSO_THEME

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


async def _ensure_agent_with_kb(db, tenant_id: str, agent_def: dict, kb: list[dict], demo_items: list[dict] | None = None):
    """Create-or-update an agent + its knowledge base (text) + optional demo items (cards).

    Idempotent design:
    - **Always overwrites** content fields (system_prompt, knowledge text, theme,
      avatar, welcome_message, icebreakers, role, goal). This ensures that every
      deploy ships the latest seeded copy without breaking existing agents.
    - **Always rebuilds** the knowledge base chunks (re-indexes the linked
      data_source) so the KB always matches the seed file.
    - **Preserves** user-edited fields: channels (tokens, verify_tokens),
      api_key, tools toggles, email_config, custom rules/tone — these are NOT
      overwritten.
    """
    name = agent_def["name"]
    existing = await db.agents.find_one(
        {"tenant_id": tenant_id, "name": {"$regex": name.split("—")[0].strip(), "$options": "i"}},
        {"_id": 0},
    )

    src_name = agent_def.get("kb_name", f"{name} — KB")

    # ----- KB upsert -----
    src = await db.data_sources.find_one(
        {"tenant_id": tenant_id, "name": src_name}, {"_id": 0, "id": 1},
    )
    if src:
        source_id = src["id"]
        # Wipe & re-index chunks (KB content may have changed)
        await db.data_chunks.delete_many({"source_id": source_id})
    else:
        source_id = str(uuid.uuid4())
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

    # ----- Demo items (cards) — optional -----
    demo_items = demo_items or []
    for p in demo_items:
        blob = (
            f"{p['title']}. Localização: {p['location']}. Tipologia {p['typology']}, "
            f"{p['area_m2']}m². {p['description']} Características: {', '.join(p['features'])}. "
            f"Palavras-chave: {p.get('search_keywords', '')}"
        )
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id, "source_id": source_id,
            "kind": "item", "title": p["title"], "text": blob,
            "meta": {
                "title": p["title"], "price": p["price"],
                "image": p["image"], "link": p["link"],
                "description": p["description"],
                "location": p["location"], "typology": p["typology"],
                "area_m2": p["area_m2"], "features": p["features"],
            },
            "indexed_at": _now(),
        })
    total = len(kb) + len(demo_items)
    await db.data_sources.update_one(
        {"id": source_id},
        {"$set": {"items": total, "chunks": total,
                  "url": agent_def.get("kb_url", ""), "indexed_at": _now()}},
    )

    # ----- Agent upsert: refresh content fields, keep user-edited config -----
    # Fields that are ALWAYS refreshed from the seed file (content):
    content_patch = {
        "name": name,
        "active": True,
        "avatar_url": agent_def.get("avatar_url", ""),
        "theme": agent_def.get("theme", {}),
        "role": agent_def.get("role", ""),
        "goal": agent_def.get("goal", ""),
        "system_prompt": agent_def["system_prompt"],
        "knowledge": "\n\n".join(c["text"] for c in kb),
        "icebreakers": agent_def.get("icebreakers", []),
        "welcome_message": agent_def.get("welcome_message", "Olá! Como posso ajudar?"),
        "default_language": "pt",
        "api_provider": "openai",
        "model_provider": "openai", "model_name": "gpt-4o-mini",
        "data_source_ids": [source_id],
        "updated_at": _now(),
    }

    if existing:
        # Se o utilizador customizou o agente via dashboard, preservamos os
        # campos de conteúdo (prompt, icebreakers, welcome, theme, knowledge).
        # Caso contrário, sincronizamos sempre com a versão do seed.
        if existing.get("is_customized"):
            # Apenas refresca metadados de fonte de dados (data_source_ids) +
            # avatar (se ainda não definido). Mantém TUDO O resto definido pelo user.
            minimal_patch = {
                "data_source_ids": [source_id],
                "updated_at": _now(),
            }
            if not existing.get("avatar_url"):
                minimal_patch["avatar_url"] = agent_def.get("avatar_url", "")
            await db.agents.update_one({"id": existing["id"]}, {"$set": minimal_patch})
            logger.info(
                f"[bootstrap] agent '{name}' is_customized=true → preservadas customizações do dashboard"
            )
        else:
            await db.agents.update_one(
                {"id": existing["id"]},
                {"$set": content_patch},
            )
            logger.info(
                f"[bootstrap] refreshed agent '{name}' ({existing['id'][:8]}…) "
                f"prompt_len={len(agent_def['system_prompt'])} ice={len(agent_def.get('icebreakers', []))} kb_chunks={len(kb)}"
            )
    else:
        agent_id = str(uuid.uuid4())
        await db.agents.insert_one({
            "id": agent_id, "tenant_id": tenant_id,
            **content_patch,
            "is_customized": False,
            "api_key": "",
            "tone": agent_def.get("tone", ""),
            "rules": agent_def.get("rules", ""),
            "tools": [{"key": "create_lead", "enabled": True}],
            "channels": {
                "webchat": {"enabled": True},
                "whatsapp": {"enabled": False},
                "telegram": {"enabled": False},
                "instagram": {"enabled": False},
                "messenger": {"enabled": False},
            },
            "email_config": {},
            "config": {"max_history": 24, "lead_capture_required": True},
            "created_at": _now(),
        })
        logger.info(f"[bootstrap] created agent '{name}' ({agent_id[:8]}…)")


async def _ensure_abby(db, tenant_id: str):
    """Provision Abby — ABBI Imóveis with full 9-property catalogue.
    Idempotent — creates from scratch on a fresh DB, or refreshes the agent's
    name/welcome/icebreakers/system_prompt on every restart so production keeps
    in sync with seed_abbi.py without touching API keys or channels."""
    abby_patch = {
        "name": "Abby — ABBI Imóveis",
        "welcome_message": "Olá! 👋 Sou a Abby da ABBI Imóveis. Posso ajudar-te a encontrar a casa certa, simular crédito ou marcar visitas.",
        "icebreakers": [
            "🏠 Comprar e simular prestação",
            "🔑 Procurar casa para arrendar",
            "📈 Imóveis para investimento",
            "📑 Que documentos preciso?",
        ],
        "theme": CONSENSO_THEME,
        "updated_at": _now(),
    }

    existing = await db.agents.find_one(
        {"tenant_id": tenant_id, "name": {"$regex": "Abby|ABBI", "$options": "i"}},
        {"_id": 0},
    )
    if existing:
        if existing.get("is_customized"):
            logger.info(f"[bootstrap] Abby is_customized=true → preservadas customizações do dashboard")
            return
        await db.agents.update_one({"id": existing["id"]}, {"$set": abby_patch})
        logger.info(
            f"[bootstrap] refreshed agent 'Abby — ABBI Imóveis' ({existing['id'][:8]}…) "
            f"ice={len(abby_patch['icebreakers'])}"
        )
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
        "is_customized": False,
        "avatar_url": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=200&h=200&fit=crop",
        "theme": CONSENSO_THEME,
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
        "api_provider": "openai", "api_key": "",
        "model_provider": "openai", "model_name": "gpt-4o-mini",
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


async def _safe_seed(label: str, fn):
    """Wrap each agent's seed call so that a failure in ONE agent doesn't
    sink the bootstrap for the others. Logs clearly which agent failed and why."""
    try:
        logger.info(f"[bootstrap] seeding {label}…")
        await fn()
        logger.info(f"[bootstrap] ✅ {label} done")
    except ImportError as e:
        logger.error(f"[bootstrap] ❌ {label} ImportError: {e} — file missing in this build?")
    except Exception as e:
        logger.error(f"[bootstrap] ❌ {label} failed: {e}", exc_info=True)


async def bootstrap(db):
    """Called once at backend startup. Idempotent — safe to re-run.
    Each agent is wrapped in its own _safe_seed so a single failure does
    NOT prevent the other agents from being provisioned."""
    try:
        tenant_id = await _ensure_admin(db)
    except Exception as e:
        logger.error(f"[bootstrap] could not ensure admin user: {e}", exc_info=True)
        return

    logger.info(f"[bootstrap] starting agent provisioning for tenant {tenant_id[:8]}…")

    # ------- Maria -------
    async def _seed_maria():
        from seed_maria import (
            AGENT_NAME as MARIA_NAME, SYSTEM_PROMPT as MARIA_PROMPT,
            ICEBREAKERS as MARIA_ICE, WELCOME_MESSAGE as MARIA_WELCOME,
            AVATAR_URL as MARIA_AVATAR, THEME as MARIA_THEME,
            KNOWLEDGE_CHUNKS as MARIA_KB, DEMO_PROPERTIES as MARIA_DEMO,
        )
        await _ensure_agent_with_kb(db, tenant_id, {
            "name": MARIA_NAME,
            "role": "Assistente IA principal da Consenso Plus — multissetorial (Imobiliário, Hotelaria, Turismo, Empresas de Serviços)",
            "goal": "Orientar visitantes do website Consenso Plus, identificar a área certa (Imobiliário, Hotelaria, Turismo ou Empresas de Serviços), qualificar leads e agendar demonstrações via https://consenso-shop.eu/marcar-reuniao.",
            "system_prompt": MARIA_PROMPT,
            "icebreakers": MARIA_ICE, "welcome_message": MARIA_WELCOME,
            "avatar_url": MARIA_AVATAR, "theme": MARIA_THEME,
            "kb_name": "Site Consenso", "kb_url": "https://consenso-shop.eu",
        }, MARIA_KB, demo_items=MARIA_DEMO)
    await _safe_seed("Maria — Assistente IA Consenso Plus", _seed_maria)

    # ------- StayLocal -------
    async def _seed_staylocal():
        from seed_staylocal import (
            SYSTEM_PROMPT as SL_PROMPT, ICEBREAKERS as SL_ICE,
            WELCOME_MESSAGE as SL_WELCOME, AVATAR_URL as SL_AVATAR,
            THEME as SL_THEME, KNOWLEDGE_CHUNKS as SL_KB,
        )
        await _ensure_agent_with_kb(db, tenant_id, {
            "name": "StayLocal Concierge AI",
            "role": "Concierge digital de hotel premium",
            "goal": "Explicar o conceito StayLocal, qualificar pedidos de reserva, recomendar experiências locais e converter em reservas.",
            "system_prompt": SL_PROMPT,
            "icebreakers": SL_ICE, "welcome_message": SL_WELCOME,
            "avatar_url": SL_AVATAR, "theme": SL_THEME,
            "kb_name": "Conceito StayLocal",
        }, SL_KB)
    await _safe_seed("StayLocal Concierge AI", _seed_staylocal)

    # ------- Tejo Sailing -------
    async def _seed_tejo():
        from seed_tejo_sailing import (
            SYSTEM_PROMPT as TJ_PROMPT, ICEBREAKERS as TJ_ICE,
            WELCOME_MESSAGE as TJ_WELCOME, AVATAR_URL as TJ_AVATAR,
            THEME as TJ_THEME, KNOWLEDGE_CHUNKS as TJ_KB,
        )
        await _ensure_agent_with_kb(db, tenant_id, {
            "name": "Tejo Sunset Sailing AI Guide",
            "role": "Concierge de luxo turístico",
            "goal": "Vender experiências de passeio de veleiro ao pôr do sol no Tejo, personalizar reservas e converter em reservas confirmadas pela equipa.",
            "system_prompt": TJ_PROMPT,
            "icebreakers": TJ_ICE, "welcome_message": TJ_WELCOME,
            "avatar_url": TJ_AVATAR, "theme": TJ_THEME,
            "kb_name": "Tejo Sunset Sailing — Experiências",
        }, TJ_KB)
    await _safe_seed("Tejo Sunset Sailing AI Guide", _seed_tejo)

    # ------- ImmoAI -------
    async def _seed_immoai():
        from seed_immoai import (
            AGENT_NAME as IMMO_NAME, SYSTEM_PROMPT as IMMO_PROMPT,
            ICEBREAKERS as IMMO_ICE, WELCOME_MESSAGE as IMMO_WELCOME,
            AVATAR_URL as IMMO_AVATAR, THEME as IMMO_THEME,
            KNOWLEDGE_CHUNKS as IMMO_KB, DEMO_PROPERTIES as IMMO_DEMO,
        )
        await _ensure_agent_with_kb(db, tenant_id, {
            "name": IMMO_NAME,
            "role": "Consultor imobiliário digital — DEMO sandbox para imobiliárias testarem o sistema",
            "goal": "Simular atendimento imobiliário real — apresentar imóveis demo, qualificar e marcar visitas. Servir como demo da Consenso Plus para imobiliárias.",
            "system_prompt": IMMO_PROMPT,
            "icebreakers": IMMO_ICE, "welcome_message": IMMO_WELCOME,
            "avatar_url": IMMO_AVATAR, "theme": IMMO_THEME,
            "kb_name": "ImmoAI — Catálogo Premium",
        }, IMMO_KB, demo_items=IMMO_DEMO)
    await _safe_seed("ImmoAI — Consultor Imobiliário Digital", _seed_immoai)

    # ------- Abby (ABBI Imóveis) — full 9-property catalogue -------
    await _safe_seed("Abby — ABBI Imóveis", lambda: _ensure_abby(db, tenant_id))

    logger.info("[bootstrap] all agent seeding complete")
