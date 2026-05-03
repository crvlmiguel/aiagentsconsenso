"""Agent Orchestrator — decides actions AND generates a structured response (reply + cards)."""
from typing import List, Dict, Any
import json
from .router import llm_complete, extract_json


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

    system = f"""{base_prompt}

Tom: {tone}.
Objetivo: {agent.get('goal', 'Ajudar o cliente')}.
Regras: {rules or 'Sê conciso. Sê honesto. Oferece transferir para humano em casos complexos.'}

Conhecimento do negócio (sempre fiável):
{knowledge or '(sem base de conhecimento adicional)'}

Dados recuperados das fontes do tenant:
{_format_context(retrieved)}

Análise da última mensagem:
- Intenção: {intent.get('intent')} | Categoria: {intent.get('category')} | Urgência: {intent.get('urgency')}
- Tipo estruturado: {structure.get('type')} | Domínio: {structure.get('domain')} | Prioridade: {structure.get('priority')}
- Necessidades: {', '.join(structure.get('needs', [])) or 'n/a'}

INSTRUÇÕES DE RESPOSTA (CRÍTICO):
- Responde SEMPRE em {reply_lang}. Se o idioma for 'pt', usa Português Europeu (pt-PT), NUNCA português do Brasil.
- Devolves APENAS JSON válido neste formato:
  {{
    "reply": "texto conversacional curto (1-3 parágrafos)",
    "cards": [
      {{"title": "...", "price": "...", "image": "https://...", "link": "https://...", "description": "..."}}
    ]
  }}
- Se houver ITENS recuperados relevantes, inclui-os como cards. Copia EXATAMENTE title/price/image/link dos dados recuperados.
- Se não houver itens relevantes, devolve "cards": [].
- Nunca inventes preços, imagens ou links.
- Nunca menciones este JSON interno ao utilizador.
"""

    turns = []
    for m in history[-10:]:
        role = "USER" if m["sender"] == "user" else "ASSISTANT"
        turns.append(f"{role}: {m['text']}")
    convo = "\n".join(turns) if turns else "(nova conversa)"

    provider = agent.get("model_provider") or "auto"
    model = agent.get("model_name") or "gpt-5.1"

    raw = await llm_complete(
        system_message=system,
        user_text=f"Histórico:\n{convo}\n\nResponde à última mensagem do utilizador em JSON.",
        session_id=f"reply-{session_id}",
        task="reasoning" if intent.get("urgency") in {"high", "urgent"} else "fast",
        provider=provider if provider != "auto" else None,
        model=model if provider != "auto" else None,
    )

    data = extract_json(raw)
    reply_text = data.get("reply") if isinstance(data, dict) else None
    cards = data.get("cards") if isinstance(data, dict) else None

    if not reply_text:
        # fallback: treat raw as plain text
        reply_text = raw if raw else "Obrigado pela sua mensagem — a nossa equipa responderá em breve."
        cards = []

    if not isinstance(cards, list):
        cards = []

    # Clean cards
    safe_cards = []
    for c in cards[:6]:
        if not isinstance(c, dict):
            continue
        safe_cards.append({
            "title": str(c.get("title", ""))[:160],
            "price": str(c.get("price", ""))[:60],
            "image": str(c.get("image", ""))[:600],
            "link": str(c.get("link", ""))[:600],
            "description": str(c.get("description", ""))[:400],
        })

    return {"reply": reply_text, "cards": safe_cards, "language": reply_lang}
