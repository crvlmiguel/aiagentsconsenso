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

INSTRUÇÕES DE RESPOSTA (CRÍTICO, OBRIGATÓRIO):
- IDIOMA: Responde SEMPRE no MESMO IDIOMA em que o cliente te escreveu (detectado: {reply_lang}). Se pt → Português Europeu (pt-PT, NUNCA pt-BR). Se en → Inglês. Se es → Espanhol. Se fr → Francês. Se de → Alemão. Se it → Italiano. Mantém o tom profissional, amigável e consultivo em qualquer idioma.
- FORMATO DA RESPOSTA: APENAS JSON válido neste formato EXATO:
  {{"reply": "mensagem 1", "follow_up": "mensagem 2 (opcional)", "cards": [{{"title": "...", "price": "...", "image": "https://...", "link": "https://...", "description": "..."}}]}}
- MENSAGENS CURTAS (CRÍTICO): mensagens devem ser CURTAS, diretas e conversacionais (estilo WhatsApp), NÃO blocos de texto longos.
  • Se a resposta for simples → UM balão em "reply" (1-2 frases, max 280 caracteres).
  • Se a resposta for mais rica (apresentar opções + pergunta qualificadora) → divide em DOIS balões: "reply" = contexto/apresentação curta, "follow_up" = pergunta ou call-to-action curto.
  • NUNCA escrevas parágrafos grandes. Prefere sempre 2 mensagens curtas a 1 mensagem longa.
- REGRAS SOBRE CARDS (NÃO QUEBRAR):
  1. Se existem [ITEM ...] nos "Dados recuperados", inclui 1-4 como cards, copiando EXATAMENTE title/price/image/link/description.
  2. NUNCA inventes preços, imagens, links ou itens. Só uses o que está nos "Dados recuperados".
  3. Se não houver [ITEM ...] relevantes, devolve "cards": [].
  4. NUNCA devolvas apenas texto sem o campo "cards" — se não houver items, "cards": [] é obrigatório.
- O campo "reply" e "follow_up" devem ser conversacionais, sem mencionar JSON, cards, ou dados internos.

EXEMPLO BOM (2 balões, curtos):
Utilizador: "Quero um T2 em Lisboa"
Dados recuperados: [ITEM 1] title=T2 Chiado ...
Resposta válida:
{{"reply": "Boa! Tenho esta opção no Chiado que pode encaixar no seu perfil.", "follow_up": "Qual o seu orçamento e se prefere zona histórica ou mais moderna?", "cards": [{{"title": "T2 Chiado", ...}}]}}

EXEMPLO MAU (evitar — 1 mensagem longa):
{{"reply": "Com base no que me diz, tenho esta excelente opção no Chiado que combina localização central, acabamentos modernos, e um preço competitivo. Gostaria de saber qual o seu orçamento aproximado e se tem preferência por zona histórica ou zona mais moderna para eu poder refinar a minha sugestão.", "cards": [...]}}
"""

    turns = []
    for m in history[-10:]:
        role = "USER" if m["sender"] == "user" else "ASSISTANT"
        turns.append(f"{role}: {m['text']}")
    convo = "\n".join(turns) if turns else "(nova conversa)"

    provider = agent.get("model_provider") or "auto"
    model = agent.get("model_name") or "gpt-5.1"

    # Force reasoning task whenever there are retrieved items (need to cite data reliably)
    has_context = bool(retrieved)
    task = "reasoning" if (has_context or intent.get("urgency") in {"high", "urgent"}) else "fast"

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
    reply_text = data.get("reply") if isinstance(data, dict) else None
    follow_up = data.get("follow_up") if isinstance(data, dict) else None
    cards = data.get("cards") if isinstance(data, dict) else None

    if not reply_text:
        # fallback: treat raw as plain text
        reply_text = raw if raw else "Obrigado pela sua mensagem — a nossa equipa responderá em breve."
        cards = []
        follow_up = None

    if not isinstance(cards, list):
        cards = []
    if follow_up is not None and not isinstance(follow_up, str):
        follow_up = None
    if follow_up:
        follow_up = follow_up.strip() or None

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

    return {"reply": reply_text, "follow_up": follow_up, "cards": safe_cards, "language": reply_lang}
