"""Webhooks inbound para Telegram e WhatsApp Cloud.
Cada agente tem tokens próprios — a rota inclui tenant_id e agent_id."""
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from models import InboundMessage

logger = logging.getLogger("consenso.webhooks")

router = APIRouter(prefix="/api/webhooks")


async def _send_telegram(bot_token: str, chat_id: int, text: str) -> dict:
    if not text:
        return {"ok": False, "error": "empty text"}
    try:
        async with httpx.AsyncClient(timeout=10) as hc:
            r = await hc.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text[:4000]},
            )
        return {"ok": r.status_code == 200, "status": r.status_code}
    except Exception as e:
        logger.warning(f"Telegram send failed: {e}")
        return {"ok": False, "error": str(e)[:200]}


async def _send_whatsapp(access_token: str, phone_number_id: str, to: str, text: str) -> dict:
    if not text:
        return {"ok": False, "error": "empty text"}
    try:
        async with httpx.AsyncClient(timeout=10) as hc:
            r = await hc.post(
                f"https://graph.facebook.com/v20.0/{phone_number_id}/messages",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": {"body": text[:4000]},
                },
            )
        ok = r.status_code == 200
        if not ok:
            logger.warning(f"WhatsApp send failed {r.status_code}: {r.text[:300]}")
        return {"ok": ok, "status": r.status_code}
    except Exception as e:
        logger.warning(f"WhatsApp send failed: {e}")
        return {"ok": False, "error": str(e)[:200]}


def build_router(db, process_inbound) -> APIRouter:
    """Create the webhooks router with injected db + _process_inbound dependency."""

    async def _get_agent(tenant_id: str, agent_id: str):
        agent = await db.agents.find_one(
            {"id": agent_id, "tenant_id": tenant_id, "active": True}, {"_id": 0}
        )
        if not agent:
            raise HTTPException(404, "Agente não encontrado ou inativo")
        return agent

    # ======================== TELEGRAM ========================
    @router.post("/telegram/{tenant_id}/{agent_id}")
    async def telegram_webhook(tenant_id: str, agent_id: str, request: Request):
        agent = await _get_agent(tenant_id, agent_id)
        ch = (agent.get("channels") or {}).get("telegram") or {}
        if not ch.get("enabled") or not ch.get("bot_token"):
            raise HTTPException(400, "Canal Telegram não configurado neste agente")

        payload = await request.json()
        msg = payload.get("message") or payload.get("edited_message") or {}
        text = msg.get("text") or ""
        frm = msg.get("from") or {}
        chat_id = (msg.get("chat") or {}).get("id")
        if not text or chat_id is None:
            return {"ok": True, "skipped": "no_text_or_chat"}

        contact_name = (
            (frm.get("first_name") or "") + " " + (frm.get("last_name") or "")
        ).strip() or frm.get("username") or "Telegram"

        inbound = InboundMessage(
            channel="telegram",
            external_user_id=f"tg-{frm.get('id', chat_id)}",
            contact_name=contact_name,
            text=text,
            agent_id=agent_id,
        )

        result = await process_inbound(tenant_id, inbound, agent_id=agent_id)
        reply = (result or {}).get("reply")
        if reply:
            await _send_telegram(ch["bot_token"], chat_id, reply)
        return {"ok": True}

    # ======================== WHATSAPP CLOUD ========================
    @router.get("/whatsapp/{tenant_id}/{agent_id}", response_class=PlainTextResponse)
    async def whatsapp_verify(
        tenant_id: str, agent_id: str,
        hub_mode: Optional[str] = None,
        hub_verify_token: Optional[str] = None,
        hub_challenge: Optional[str] = None,
        request: Request = None,
    ):
        """Meta webhook verification (GET).
        Reads query: hub.mode, hub.verify_token, hub.challenge.
        We accept dotted query keys via request.query_params."""
        qp = request.query_params if request else {}
        mode = qp.get("hub.mode") or hub_mode
        token = qp.get("hub.verify_token") or hub_verify_token
        challenge = qp.get("hub.challenge") or hub_challenge

        agent = await _get_agent(tenant_id, agent_id)
        ch = (agent.get("channels") or {}).get("whatsapp") or {}
        expected = (ch.get("verify_token") or "").strip()
        if mode == "subscribe" and expected and token == expected:
            return PlainTextResponse(challenge or "")
        raise HTTPException(403, "Verificação falhou")

    @router.post("/whatsapp/{tenant_id}/{agent_id}")
    async def whatsapp_webhook(tenant_id: str, agent_id: str, request: Request):
        agent = await _get_agent(tenant_id, agent_id)
        ch = (agent.get("channels") or {}).get("whatsapp") or {}
        if not ch.get("enabled") or not ch.get("access_token") or not ch.get("phone_number_id"):
            raise HTTPException(400, "Canal WhatsApp não configurado neste agente")

        payload = await request.json()
        # Meta payload structure: entry[].changes[].value.messages[]
        results = []
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                contacts = {c.get("wa_id"): c for c in value.get("contacts") or []}
                for m in value.get("messages") or []:
                    wa_id = m.get("from")
                    if not wa_id:
                        continue
                    # Only handle text messages for now
                    text = ""
                    if m.get("type") == "text":
                        text = (m.get("text") or {}).get("body") or ""
                    elif m.get("type") == "button":
                        text = (m.get("button") or {}).get("text") or ""
                    elif m.get("type") == "interactive":
                        interactive = m.get("interactive") or {}
                        text = (
                            (interactive.get("button_reply") or {}).get("title")
                            or (interactive.get("list_reply") or {}).get("title")
                            or ""
                        )
                    if not text:
                        continue

                    profile = (contacts.get(wa_id) or {}).get("profile") or {}
                    contact_name = profile.get("name") or f"+{wa_id}"

                    inbound = InboundMessage(
                        channel="whatsapp",
                        external_user_id=f"wa-{wa_id}",
                        contact_name=contact_name,
                        text=text,
                        agent_id=agent_id,
                    )
                    result = await process_inbound(tenant_id, inbound, agent_id=agent_id)
                    reply = (result or {}).get("reply")
                    if reply:
                        await _send_whatsapp(ch["access_token"], ch["phone_number_id"], wa_id, reply)
                    results.append({"wa_id": wa_id, "processed": True})
        return {"ok": True, "results": results}

    return router
