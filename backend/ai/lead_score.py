"""Lead Scoring 0-100 — determinístico, baseado em sinais da conversa e do lead.

Não usa LLM. Combina sinais explícitos da conversa + dados do lead criado.
Atualiza o documento `lead.score` automaticamente após cada turno.
"""
import re
from typing import Optional


def compute_lead_score(
    conversation: Optional[dict] = None,
    lead: Optional[dict] = None,
    history: Optional[list] = None,
) -> dict:
    """Calcula score 0-100 do lead com base em sinais detetáveis.

    Returns:
        {"score": int, "tier": "frio"|"morno"|"quente", "signals": [str]}
    """
    score = 0
    signals = []
    conversation = conversation or {}
    lead = lead or {}
    history = history or []
    qual = conversation.get("qualification") or {}

    # ===== 1. Dados pessoais (até 30 pontos) =====
    if lead.get("name") or qual.get("lead", {}).get("name"):
        score += 10
        signals.append("Nome partilhado")
    if lead.get("email") or qual.get("lead", {}).get("email"):
        score += 15
        signals.append("Email partilhado")
    if lead.get("phone"):
        score += 5
        signals.append("Telefone partilhado")

    # ===== 2. Especificidade da procura (até 30 pontos) =====
    search = qual.get("search") or {}
    if search.get("property_type"):
        score += 10
        signals.append(f"Tipologia definida ({search['property_type']})")
    if search.get("zone"):
        score += 10
        signals.append(f"Zona definida ({search['zone']})")
    if qual.get("budget"):
        score += 10
        signals.append(f"Orçamento partilhado ({qual['budget']})")

    # ===== 3. Sinais comportamentais (até 30 pontos) =====
    user_msgs = [m for m in history if m.get("sender") == "user"]
    n_user_turns = len(user_msgs)
    if n_user_turns >= 3:
        score += 5
        signals.append(f"Engajamento ({n_user_turns} mensagens)")
    if n_user_turns >= 7:
        score += 5

    # Texto completo do utilizador para regex
    all_user_text = " ".join((m.get("text") or "") for m in user_msgs).lower()
    urgency_re = re.compile(
        r"\b(urgente|rapidamente|esta semana|imediato|j[áa]|asap|"
        r"esta semana|este m[êe]s|j[áa] decidi|prioridade)\b", re.IGNORECASE)
    if urgency_re.search(all_user_text):
        score += 8
        signals.append("Urgência detetada")

    # Visita marcada — sinal muito forte
    if (lead.get("tags") and "visita-marcada" in lead.get("tags", [])) or \
       qual.get("status") == "visita_agendada":
        score += 12
        signals.append("Visita marcada")
    elif qual.get("status") == "credito_simulado":
        score += 8
        signals.append("Simulação de crédito feita")

    # ===== 4. Perfil de qualidade (até 10 pontos) =====
    profile = qual.get("profile")
    if profile == "Investidor":
        score += 5
        signals.append("Perfil investidor")
    elif profile == "Precisa de Crédito":
        score += 3
        signals.append("Necessita financiamento")
    elif profile == "Habitação Própria":
        score += 5
        signals.append("Habitação própria")

    # Clamp 0-100
    score = max(0, min(100, score))

    # Tier classification
    if score >= 70:
        tier = "quente"
    elif score >= 40:
        tier = "morno"
    else:
        tier = "frio"

    return {"score": score, "tier": tier, "signals": signals}
