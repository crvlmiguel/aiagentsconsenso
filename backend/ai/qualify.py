"""CRM Qualification Engine — analisa uma conversa e produz:
- Estado do funil (Novo / Qualificando / Qualificado / Crédito Simulado / Visita Agendada)
- Resumo estruturado (lead, procura, orçamento, perfil)
- Tags secundárias de atributos (T3, Braga, Urgente, ...)
- Resumo curto da conversa (1-2 frases)
"""
from typing import Optional
from .router import llm_complete, extract_json

# Estados do funil (canónicos, em PT-PT)
FUNNEL_STATES = ["novo", "qualificando", "qualificado", "credito_simulado", "visita_agendada"]

QUALIFY_SYSTEM = """És um motor de qualificação CRM para agentes imobiliários em Portugal.
A tua tarefa: analisar uma conversa entre cliente e agente e devolver um JSON estruturado.

Schema (estrito, devolve APENAS JSON válido, sem prosa):
{
  "status": "novo" | "qualificando" | "qualificado" | "credito_simulado" | "visita_agendada",
  "lead": { "name": string|null, "email": string|null },
  "search": { "property_type": string|null, "zone": string|null },
  "budget": string|null,
  "profile": "Investidor" | "Habitação Própria" | "Precisa de Crédito" | null,
  "tags": [string, ...],
  "summary": string
}

Regras OBRIGATÓRIAS:
- "status": deriva-o do conteúdo da conversa:
  • "novo": cliente acabou de chegar, sem informação capturada.
  • "qualificando": já partilhou *parte* da informação (nome OU email OU tipo de imóvel OU zona OU orçamento).
  • "qualificado": tem nome + email + (tipo de imóvel OU zona OU orçamento).
  • "credito_simulado": foi feita uma simulação de crédito habitação na conversa.
  • "visita_agendada": foi confirmada uma visita a um imóvel (data ou intenção clara).
  Escolhe SEMPRE o estado mais avançado aplicável.
- "lead.name" e "lead.email": só preencher quando explicitamente partilhados. Caso contrário null.
- "search.property_type": tipologia (ex: "T2", "T3", "Moradia V4", "Apartamento"). null se desconhecido.
- "search.zone": zona/cidade procurada (ex: "Lisboa", "Braga", "Cascais"). null se desconhecido.
- "budget": valor máximo em texto curto (ex: "350 000€", "até 500k"). null se desconhecido.
- "profile": classifica em "Investidor" (procura rendimento/arrendamento), "Habitação Própria" (vai morar) ou "Precisa de Crédito" (mencionou financiamento/banca). null se ambíguo.
- "tags": ATRIBUTOS curtos e únicos para filtros (NÃO repetir o status). Exemplos válidos: "T3", "Braga", "Urgente", "Pronto-a-habitar", "Com piscina", "Investimento". Máximo 5. Tudo em PT-PT, kebab/title case curto.
- "summary": resumo de 1 a 2 frases, em PT-PT, factual, descrevendo o que o cliente procura e em que ponto está a conversa.

NUNCA inventes dados. Se não foi mencionado, devolve null/[]/"".
Devolve APENAS o JSON."""


def _normalize(d: dict) -> dict:
    """Garante schema estável mesmo se o LLM falhar/desviar."""
    status = (d.get("status") or "novo").lower().strip()
    if status not in FUNNEL_STATES:
        status = "novo"
    lead = d.get("lead") or {}
    if not isinstance(lead, dict):
        lead = {}
    search = d.get("search") or {}
    if not isinstance(search, dict):
        search = {}
    profile = d.get("profile")
    if profile not in ("Investidor", "Habitação Própria", "Precisa de Crédito", None):
        profile = None
    tags = d.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    # Filtra duplicados, valores vazios, e remove qualquer tag igual ao status
    seen = set()
    clean_tags = []
    for t in tags:
        if not isinstance(t, str):
            continue
        t = t.strip()
        if not t:
            continue
        # banir tags genéricas legadas
        if t.lower() in {"sales", "general", "support", "billing", "technical", "other",
                         "high", "urgent", "low", "medium"}:
            continue
        if t.lower() in {s.replace("_", " ") for s in FUNNEL_STATES}:
            continue
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        clean_tags.append(t)
        if len(clean_tags) >= 5:
            break
    return {
        "status": status,
        "lead": {
            "name": (lead.get("name") or None) if isinstance(lead.get("name"), str) and lead.get("name").strip() else None,
            "email": (lead.get("email") or None) if isinstance(lead.get("email"), str) and lead.get("email").strip() else None,
        },
        "search": {
            "property_type": (search.get("property_type") or None) if isinstance(search.get("property_type"), str) and search.get("property_type").strip() else None,
            "zone": (search.get("zone") or None) if isinstance(search.get("zone"), str) and search.get("zone").strip() else None,
        },
        "budget": (d.get("budget") or None) if isinstance(d.get("budget"), str) and d.get("budget").strip() else None,
        "profile": profile,
        "tags": clean_tags,
        "summary": (d.get("summary") or "").strip()[:300],
    }


def _format_history(history: list[dict], limit: int = 24) -> str:
    """Formata as últimas N mensagens para o LLM."""
    rows = []
    for m in history[-limit:]:
        role = m.get("sender") or "user"
        if role == "ai":
            label = "Agente"
        elif role == "human":
            label = "Operador humano"
        else:
            label = "Cliente"
        text = (m.get("text") or "").strip()
        if not text:
            continue
        rows.append(f"{label}: {text}")
    return "\n".join(rows) or "(conversa vazia)"


async def qualify_conversation(
    history: list[dict],
    session_id: str,
    api_provider: str = "emergent",
    api_key: str = "",
) -> dict:
    """Corre o LLM e devolve um snapshot de qualificação normalizado."""
    convo_text = _format_history(history)
    try:
        out = await llm_complete(
            system_message=QUALIFY_SYSTEM,
            user_text=f"Conversa:\n{convo_text}\n\nDevolve APENAS o JSON.",
            session_id=f"qualify-{session_id}",
            task="fast",
            api_provider=api_provider,
            api_key=api_key,
        )
        data = extract_json(out) or {}
    except Exception:
        data = {}
    return _normalize(data)
