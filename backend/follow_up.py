"""WhatsApp Follow-up automático para leads — scheduler em background.

Cadência: 24h, 3 dias, 7 dias após criação do lead, se o agente tiver WhatsApp ativo
e o lead tiver telefone + score >= 40 (morno/quente).

Configurável por agente via `agent.config.follow_up_enabled` (default True).
"""
import logging
import asyncio
from datetime import datetime, timezone, timedelta
import httpx

logger = logging.getLogger(__name__)


# Cadência de follow-up: (delta horas, índice tag, template_fn)
FOLLOWUP_STEPS = [
    {"after_hours": 24,   "tag": "fu1",  "label": "24h"},
    {"after_hours": 72,   "tag": "fu2",  "label": "3 dias"},
    {"after_hours": 168,  "tag": "fu3",  "label": "7 dias"},
]


def _build_message(lead: dict, step: dict, language: str = "pt") -> str:
    """Constrói a mensagem de follow-up baseada no step e idioma."""
    name = (lead.get("name") or "").split(" ")[0] or "olá"

    templates_pt = {
        "fu1": (
            f"Olá {name}! 👋 Ainda interessado nos imóveis que mostrámos? "
            f"Posso ajudar a marcar uma visita ou enviar mais opções. 🏠"
        ),
        "fu2": (
            f"Olá {name}, tudo bem? Apareceram novos imóveis que podem encaixar no teu perfil. "
            f"Queres dar uma olhada? 👀"
        ),
        "fu3": (
            f"Olá {name}, última nota: a equipa está disponível esta semana para mostrar "
            f"propriedades de luxo. Bastam 15 minutos. Quando te convém? 📅"
        ),
    }

    templates_en = {
        "fu1": f"Hi {name}! 👋 Still interested in the properties we showed you? Happy to book a viewing or send new options. 🏠",
        "fu2": f"Hi {name}, hope you're well. New listings just came in that match your profile. Want a look? 👀",
        "fu3": f"Hi {name}, our team has slots this week to show you premium properties. Just 15 minutes. When works for you? 📅",
    }

    book = templates_en if language == "en" else templates_pt
    return book.get(step["tag"], book["fu1"])


async def send_whatsapp(channel_cfg: dict, to_phone: str, text: str) -> dict:
    """Envia mensagem via WhatsApp Cloud API. Retorna {ok, error?}."""
    access_token = channel_cfg.get("access_token")
    phone_id = channel_cfg.get("phone_number_id")
    if not access_token or not phone_id:
        return {"ok": False, "error": "WhatsApp não configurado"}

    # Normaliza telefone (remove espaços, mantém +)
    to = (to_phone or "").replace(" ", "").replace("-", "")
    if not to:
        return {"ok": False, "error": "Sem telefone"}

    url = f"https://graph.facebook.com/v20.0/{phone_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text[:1000]},
    }
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code >= 400:
                return {"ok": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
            return {"ok": True, "response": r.json()}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


async def run_followup_tick(db) -> dict:
    """Tick único do scheduler: processa todos os leads pendentes de follow-up.
    Retorna estatísticas {checked, sent, errors}."""
    now = datetime.now(timezone.utc)
    sent_count = 0
    errors = 0
    checked = 0

    # Para cada step, vai buscar leads criados há (after_hours) que ainda não receberam o step
    for step in FOLLOWUP_STEPS:
        cutoff = now - timedelta(hours=step["after_hours"])
        cutoff_max = now - timedelta(hours=step["after_hours"] + 24)  # janela 24h
        cutoff_iso = cutoff.isoformat()
        cutoff_max_iso = cutoff_max.isoformat()

        leads_cur = db.leads.find({
            "created_at": {"$lte": cutoff_iso, "$gte": cutoff_max_iso},
            "phone": {"$ne": None, "$exists": True},
            "score": {"$gte": 40},  # só morno/quente
            "followup_steps": {"$ne": step["tag"]},  # ainda não enviado
            "followup_disabled": {"$ne": True},
        }, {"_id": 0}).limit(50)

        async for lead in leads_cur:
            checked += 1
            agent_id = lead.get("agent_id")
            if not agent_id:
                continue
            agent = await db.agents.find_one({"id": agent_id}, {"_id": 0})
            if not agent:
                continue

            cfg = (agent.get("config") or {})
            if cfg.get("follow_up_enabled") is False:
                continue

            wa = (agent.get("channels") or {}).get("whatsapp") or {}
            if not wa.get("enabled"):
                continue

            lang = lead.get("language") or "pt"
            text = _build_message(lead, step, lang)
            result = await send_whatsapp(wa, lead.get("phone", ""), text)

            update_set = {"followup_last_at": now.isoformat()}
            if result.get("ok"):
                sent_count += 1
                update_op = {
                    "$addToSet": {"followup_steps": step["tag"]},
                    "$set": update_set,
                }
                logger.info(f"Follow-up {step['label']} sent to lead {lead['id'][:8]} ({lead.get('phone')})")
            else:
                errors += 1
                update_op = {
                    "$set": {**update_set, "followup_last_error": result.get("error", "")[:300]},
                }
                logger.warning(f"Follow-up {step['label']} failed for lead {lead['id'][:8]}: {result.get('error')}")

            await db.leads.update_one({"id": lead["id"]}, update_op)

    return {"checked": checked, "sent": sent_count, "errors": errors}


async def scheduler_loop(db, interval_seconds: int = 600):
    """Loop principal do scheduler — corre forever, tick a cada 10 min."""
    logger.info(f"WhatsApp follow-up scheduler started (interval={interval_seconds}s)")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            stats = await run_followup_tick(db)
            if stats["sent"] > 0 or stats["errors"] > 0:
                logger.info(f"Follow-up tick: {stats}")
        except asyncio.CancelledError:
            logger.info("Follow-up scheduler cancelled")
            return
        except Exception as e:
            logger.warning(f"Follow-up scheduler error: {e}")
            await asyncio.sleep(60)
