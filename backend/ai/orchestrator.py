"""Agent Orchestrator — decides actions AND generates a structured response (reply + cards)."""
import logging
import re
from typing import List, Dict, Any
from .router import llm_complete, extract_json

logger = logging.getLogger(__name__)


def _retrieved_to_cards(retrieved: List[dict], limit: int = 3) -> List[dict]:
    """Builds cards directly from retrieved items metadata (failure-safe fallback)."""
    out = []
    for d in retrieved or []:
        if d.get("kind") != "item":
            continue
        meta = d.get("meta") or {}
        if not meta.get("title"):
            continue
        out.append({
            "title": str(meta.get("title", ""))[:160],
            "price": str(meta.get("price", ""))[:60],
            "image": str(meta.get("image", ""))[:600],
            "link": str(meta.get("link", ""))[:600],
            "description": str(meta.get("description", ""))[:400],
        })
        if len(out) >= limit:
            break
    return out


def decide_actions(intent: dict, structure: dict, agent: dict) -> Dict[str, Any]:
    enabled_tools = {t["key"] for t in agent.get("tools", []) if t.get("enabled")}
    actions: List[Dict[str, Any]] = []

    domain = structure.get("domain", "general")
    typ = structure.get("type", "inquiry")
    priority = structure.get("priority", "medium")
    entities = structure.get("entities", {}) or {}

    if typ == "lead" or domain == "sales" or intent.get("intent") in {"sales_inquiry", "pricing", "booking"}:
        if "create_lead" in enabled_tools:
            actions.append({
                "tool": "create_lead",
                "payload": {
                    "name": entities.get("name") or structure.get("business_context", "Novo Lead")[:60],
                    "email": entities.get("email"),
                    "phone": entities.get("phone"),
                    "company": entities.get("company"),
                    "notes": structure.get("business_context", ""),
                },
            })

    if typ == "ticket" or domain == "support" or intent.get("intent") in {"support_request", "complaint"}:
        if "create_ticket" in enabled_tools:
            actions.append({
                "tool": "create_ticket",
                "payload": {
                    "subject": (structure.get("business_context") or intent.get("intent", "Suporte"))[:80],
                    "description": structure.get("business_context", ""),
                    "priority": priority,
                },
            })

    response_mode = "reply"
    if priority in {"urgent", "high"} and intent.get("intent") == "complaint":
        response_mode = "reply_and_notify"

    return {"actions": actions, "response_mode": response_mode}


def _format_context(retrieved: List[dict]) -> str:
    if not retrieved:
        return "(nenhuma fonte de dados correspondente)"
    lines = []
    for i, d in enumerate(retrieved, 1):
        meta = d.get("meta", {}) or {}
        if d.get("kind") == "item":
            lines.append(
                f"[ITEM {i}] title={meta.get('title','')} | price={meta.get('price','')} | link={meta.get('link','')} | image={meta.get('image','')} | description={meta.get('description','')}"
            )
        else:
            lines.append(f"[TEXT {i}] {d.get('text','')[:500]}")
    return "\n".join(lines)


async def generate_response(
    agent: dict,
    history: list,
    intent: dict,
    structure: dict,
    retrieved: List[dict],
    language: str,
    session_id: str,
) -> Dict[str, Any]:
    """Return {reply: str, cards: [...], language: str}."""
    tone = agent.get("tone", "professional")
    rules = agent.get("rules", "")
    knowledge = agent.get("knowledge", "")
    base_prompt = agent.get("system_prompt") or "És um assistente útil."
    default_lang = agent.get("default_language") or "pt"

    reply_lang = language or default_lang

    # Pre-build cards from retrieved items — saves the LLM ~500-800 output tokens
    # (which translates to ~2-3 seconds on gemini-flash). The LLM only needs to
    # decide WHICH items match (by referring to them by index) and produce the reply.
    server_cards = _retrieved_to_cards(retrieved, limit=4)
    items_summary = ""
    if server_cards:
        lines = []
        for i, c in enumerate(server_cards, 1):
            lines.append(f"[{i}] {c['title']} | {c.get('price','')} | {c.get('description','')[:100]}")
        items_summary = "\n".join(lines)

    system = f"""{base_prompt}

Tom: {tone}.
Objetivo: {agent.get('goal', 'Ajudar o cliente')}.
Regras: {rules or 'Sê conciso. Sê honesto.'}

{f"Imóveis disponíveis nas fontes:{chr(10)}{items_summary}" if items_summary else ""}
{f"Conhecimento adicional: {knowledge}" if knowledge else ""}

INSTRUÇÕES (CRÍTICO):
- IDIOMA: responde no mesmo idioma do cliente (detectado: {reply_lang}; se pt → pt-PT, NUNCA pt-BR).
- FORMATO: APENAS JSON: {{"reply": "msg1 curta", "follow_up": "msg2 curta opcional", "use_items": [1,2]}}
- MENSAGENS CURTAS (estilo WhatsApp): 1-2 frases, max 280 chars cada balão. Sem parágrafos.
- "use_items" é uma lista com os números [1..N] dos imóveis que queres mostrar como cards. Lista vazia [] se nenhum encaixa.
- NÃO copies título/preço/link no reply — eles aparecem nos cards automaticamente.
- "reply" e "follow_up" devem ser conversacionais, NUNCA listas de imóveis.

EXEMPLO:
Cliente: "Quero T2 em Lagos"
Imóveis: [1] T2 Jardim de Lagos | Sob consulta...
JSON: {{"reply": "Boa! Tenho esta opção em Lagos que encaixa.", "follow_up": "Qual o teu orçamento?", "use_items": [1]}}
"""

    turns = []
    for m in history[-10:]:
        role = "USER" if m["sender"] == "user" else "ASSISTANT"
        turns.append(f"{role}: {m['text']}")
    convo = "\n".join(turns) if turns else "(nova conversa)"

    provider = agent.get("model_provider") or "auto"
    model = agent.get("model_name") or "gpt-5.1"

    # Default to "fast" (gemini-2.5-flash) for sub-second responses.
    # Only escalate to "reasoning" (gpt-5.1) for genuine complaints or urgent cases
    # where higher reasoning quality matters more than speed.
    is_complaint_urgent = (
        intent.get("urgency") in {"high", "urgent"}
        and intent.get("intent") in {"complaint", "support_request"}
    )
    task = "reasoning" if is_complaint_urgent else "fast"

    raw = await llm_complete(
        system_message=system,
        user_text=f"Histórico:\n{convo}\n\nResponde à última mensagem do utilizador em JSON.",
        session_id=f"reply-{session_id}",
        task=task,
        provider=provider if provider != "auto" else None,
        model=model if provider != "auto" else None,
        api_provider=agent.get("api_provider") or "emergent",
        api_key=agent.get("api_key") or "",
    )

    data = extract_json(raw)

    # One-shot retry: if JSON parsing failed but the LLM clearly responded,
    # ask it once more to RE-emit the same response strictly as JSON.
    if (not isinstance(data, dict) or not data.get("reply")) and raw and len(raw) > 10:
        try:
            raw2 = await llm_complete(
                system_message=(
                    "Recebes um texto e tens de o devolver APENAS como JSON válido no formato "
                    '{"reply": str, "follow_up": str|null, "use_items": [int]}. '
                    "NUNCA uses markdown. NUNCA expliques. Devolve SÓ o JSON."
                ),
                user_text=f"Texto a converter em JSON:\n{raw}\n\nDevolve APENAS o JSON.",
                session_id=f"reply-fix-{session_id}",
                task="fast",
                api_provider=agent.get("api_provider") or "emergent",
                api_key=agent.get("api_key") or "",
            )
            data2 = extract_json(raw2)
            if isinstance(data2, dict) and data2.get("reply"):
                data = data2
        except Exception as e:
            logger.warning(f"orchestrator JSON retry failed: {e}")

    reply_text = data.get("reply") if isinstance(data, dict) else None
    follow_up = data.get("follow_up") if isinstance(data, dict) else None
    use_items = data.get("use_items") if isinstance(data, dict) else None
    # Backward compat: accept legacy "cards" array if the LLM returned it
    legacy_cards = data.get("cards") if isinstance(data, dict) else None

    if not reply_text:
        # Fallback: short generic reply + auto-attach top retrieved cards
        if server_cards:
            reply_text = "Aqui estão algumas opções que podem encaixar 👇"
            follow_up = "Qual destas te interessa mais?"
            use_items = list(range(1, len(server_cards) + 1))
        else:
            reply_text = "Obrigado pela sua mensagem — a equipa responderá em breve."

    if follow_up is not None and not isinstance(follow_up, str):
        follow_up = None
    if follow_up:
        follow_up = follow_up.strip() or None

    # Resolve cards: prefer use_items index list (new schema) → server-prebuilt cards
    safe_cards = []
    if isinstance(use_items, list):
        for idx in use_items[:6]:
            try:
                i = int(idx) - 1
                if 0 <= i < len(server_cards):
                    safe_cards.append(server_cards[i])
            except (ValueError, TypeError):
                continue
    elif isinstance(legacy_cards, list):
        # Fall back to legacy schema (LLM emitted full card objects)
        for c in legacy_cards[:6]:
            if not isinstance(c, dict):
                continue
            safe_cards.append({
                "title": str(c.get("title", ""))[:160],
                "price": str(c.get("price", ""))[:60],
                "image": str(c.get("image", ""))[:600],
                "link": str(c.get("link", ""))[:600],
                "description": str(c.get("description", ""))[:400],
            })

    # Safety net: reply mentions properties but no cards attached → auto-attach top items
    if not safe_cards and server_cards:
        looks_like_listing = any(s in (reply_text or "").lower() for s in
                                 ["moradia", "apartamento", "imóvel", "imovel",
                                  "t1", "t2", "t3", "t4", "v1", "v2", "v3", "v4",
                                  "opção", "opções", "encaixa", "tenho"])
        if looks_like_listing:
            safe_cards = server_cards[:3]

    return {"reply": reply_text, "follow_up": follow_up, "cards": safe_cards, "language": reply_lang}


# ============================================================================
# STREAMING VARIANT — yields events for SSE-driven progressive rendering.
# Same contract as generate_response (JSON {reply, follow_up, use_items}) but
# extracts the `reply` field incrementally so the UI can paint tokens live.
# ============================================================================

import json as _json
from ai.router import llm_stream  # noqa: E402  (intentional: only needed for streaming)


def _extract_partial_reply(buffer: str) -> str:
    """Given a buffer that contains '"reply"\\s*:\\s*"<chars>...' (possibly incomplete),
    return the current decoded value of the reply field. Handles JSON escapes.
    Returns "" if reply field hasn't started yet."""
    m = re.search(r'"reply"\s*:\s*"', buffer)
    if not m:
        return ""
    start = m.end()
    # Walk until matching unescaped quote (or end of buffer)
    i = start
    out = []
    while i < len(buffer):
        ch = buffer[i]
        if ch == "\\" and i + 1 < len(buffer):
            nxt = buffer[i + 1]
            esc_map = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}
            if nxt in esc_map:
                out.append(esc_map[nxt])
                i += 2
                continue
            if nxt == "u" and i + 5 < len(buffer):
                try:
                    out.append(chr(int(buffer[i+2:i+6], 16)))
                    i += 6
                    continue
                except ValueError:
                    break
            # Incomplete escape — stop, wait for next chunk
            break
        if ch == '"':
            return "".join(out)
        out.append(ch)
        i += 1
    return "".join(out)


async def generate_response_stream(
    agent: dict,
    history: list,
    intent: dict,
    structure: dict,
    retrieved: List[dict],
    language: str,
    session_id: str,
):
    """Async generator yielding events:
      {"type": "chunk", "text": "delta"} — reply token deltas (progressive)
      {"type": "done", "reply": str, "follow_up": str|None, "cards": list, "language": str}

    Falls back to non-streaming generate_response on any error (caller decides how to expose).
    """
    tone = agent.get("tone", "professional")
    rules = agent.get("rules", "")
    knowledge = agent.get("knowledge", "")
    base_prompt = agent.get("system_prompt") or "És um assistente útil."
    default_lang = agent.get("default_language") or "pt"
    reply_lang = language or default_lang

    server_cards = _retrieved_to_cards(retrieved, limit=4)
    items_summary = ""
    if server_cards:
        lines = []
        for i, c in enumerate(server_cards, 1):
            lines.append(f"[{i}] {c['title']} | {c.get('price','')} | {c.get('description','')[:100]}")
        items_summary = "\n".join(lines)

    system = f"""{base_prompt}

Tom: {tone}.
Objetivo: {agent.get('goal', 'Ajudar o cliente')}.
Regras: {rules or 'Sê conciso. Sê honesto.'}

{f"Imóveis disponíveis nas fontes:{chr(10)}{items_summary}" if items_summary else ""}
{f"Conhecimento adicional: {knowledge}" if knowledge else ""}

INSTRUÇÕES (CRÍTICO):
- IDIOMA: responde no mesmo idioma do cliente (detectado: {reply_lang}; se pt → pt-PT, NUNCA pt-BR).
- FORMATO: APENAS JSON: {{"reply": "msg1 curta", "follow_up": "msg2 curta opcional", "use_items": [1,2]}}
- EMITE O CAMPO "reply" PRIMEIRO (antes de follow_up e use_items) — isto é OBRIGATÓRIO.
- MENSAGENS CURTAS (estilo WhatsApp): 1-2 frases, max 280 chars cada balão.
- "use_items" é uma lista [1..N] dos imóveis para mostrar como cards. Lista vazia [] se nenhum encaixa.
- NÃO copies título/preço/link no reply — eles aparecem nos cards automaticamente.
"""

    turns = []
    for m in history[-10:]:
        role = "USER" if m["sender"] == "user" else "ASSISTANT"
        turns.append(f"{role}: {m['text']}")
    convo = "\n".join(turns) if turns else "(nova conversa)"

    # Stream raw tokens
    buffer = ""
    last_emitted = ""
    try:
        async for delta in llm_stream(
            system_message=system,
            user_text=f"Histórico:\n{convo}\n\nResponde à última mensagem do utilizador em JSON.",
            api_provider=agent.get("api_provider") or "openai",
            api_key=agent.get("api_key") or "",
            model=agent.get("model_name") or "gpt-4o-mini",
        ):
            buffer += delta
            # Try to extract the current reply value
            current = _extract_partial_reply(buffer)
            if current and current != last_emitted and len(current) > len(last_emitted):
                yield {"type": "chunk", "text": current[len(last_emitted):]}
                last_emitted = current
    except Exception as e:
        logger.warning(f"stream failed, falling back: {e}")
        # Fallback to non-streaming generate_response
        full = await generate_response(agent, history, intent, structure, retrieved, language, session_id)
        if last_emitted == "" and full.get("reply"):
            yield {"type": "chunk", "text": full["reply"]}
        yield {"type": "done", **full}
        return

    # Parse final JSON
    data = extract_json(buffer) or {}
    reply_text = data.get("reply") or last_emitted or "Obrigado pela sua mensagem."
    follow_up = data.get("follow_up")
    use_items = data.get("use_items")

    if follow_up is not None and not isinstance(follow_up, str):
        follow_up = None
    if follow_up:
        follow_up = follow_up.strip() or None

    safe_cards = []
    if isinstance(use_items, list):
        for idx in use_items[:6]:
            try:
                i = int(idx) - 1
                if 0 <= i < len(server_cards):
                    safe_cards.append(server_cards[i])
            except (ValueError, TypeError):
                continue

    if not safe_cards and server_cards:
        looks_like_listing = any(s in (reply_text or "").lower() for s in
                                 ["moradia", "apartamento", "imóvel", "imovel",
                                  "t1", "t2", "t3", "t4", "v1", "v2", "v3", "v4",
                                  "opção", "opções", "encaixa", "tenho"])
        if looks_like_listing:
            safe_cards = server_cards[:3]

    # If we never streamed a reply char (e.g. LLM emitted use_items first), emit it now
    if last_emitted == "" and reply_text:
        yield {"type": "chunk", "text": reply_text}

    yield {
        "type": "done",
        "reply": reply_text, "follow_up": follow_up,
        "cards": safe_cards, "language": reply_lang,
    }
