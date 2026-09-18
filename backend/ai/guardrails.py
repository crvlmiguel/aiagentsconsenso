"""Guardrails aplicados APÓS o LLM gerar a resposta.

Objectivos:
1. Impedir re-perguntas sobre campos já capturados (users, name, email…)
2. Filtrar URLs — apenas domínios da whitelist do agente (se definida)
3. Substituir URLs de agendamento inventados pelo link oficial do agente
4. Detectar respostas duplicadas (mesma pergunta repetida ao utilizador)
"""
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Regex de URL — inclui https://, http:// e domínios "nus" com TLD conhecido
_URL_RE = re.compile(
    r"https?://[^\s\]\)\}\>\"'`]+"
    r"|(?<!@)\b(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+\.[a-z]{2,}"
    r"(?:/[^\s\]\)\}\>\"'`]*)?",
    re.IGNORECASE,
)

# Domínios sempre permitidos por defeito (marca Consenso).
_DEFAULT_ALLOWED = {
    "consenso-plus.com",
    "consenso-shop.eu",
    "consenso-global.com",
    "consenso-agents.com",
    "consensoglobal.pipedrive.com",
}

# Palavras que sinalizam intenção de agendamento
_SCHEDULE_INTENT_KEYWORDS = (
    "agenda", "agendar", "marcar reunião", "marcar reuniao", "marcar visita",
    "reunião", "reuniao", "demonstração", "demonstracao", "demo",
    "book a meeting", "schedule a call", "calendário", "calendario",
    "que dia", "que hora", "disponibilidade",
)


def _normalize_domain(host: Optional[str]) -> str:
    if not host:
        return ""
    return host.lower().lstrip(".").lstrip("www.")


def _is_domain_allowed(url: str, allow: set) -> bool:
    """True se o URL pertencer a algum domínio (ou subdomínio) permitido."""
    try:
        host = _normalize_domain(urlparse(
            url if url.startswith("http") else "http://" + url
        ).hostname or "")
        if not host:
            return False
        for allowed in allow:
            a = _normalize_domain(allowed)
            if host == a or host.endswith("." + a):
                return True
        return False
    except Exception:
        return False


def filter_urls_by_whitelist(
    text: str,
    allowed_domains: Optional[List[str]] = None,
    scheduling_link: Optional[str] = None,
) -> str:
    """Remove URLs que não estão na whitelist do agente.
    - Se `allowed_domains` for None ou lista vazia → não filtra nada (backward-compat).
    - `scheduling_link` é adicionado à whitelist automaticamente."""
    if not text or not allowed_domains:
        return text
    allow_set = set(_DEFAULT_ALLOWED) | {d.lower() for d in allowed_domains if d}
    if scheduling_link:
        try:
            host = urlparse(scheduling_link).hostname
            if host:
                allow_set.add(host.lower())
        except Exception:
            pass

    removed: List[str] = []

    def _replace(match: re.Match) -> str:
        url = match.group(0)
        # Ignorar emails
        if "@" in url or url.count("/") == 0:
            return url
        if _is_domain_allowed(url, allow_set):
            return url
        removed.append(url)
        return ""  # remove URL não permitido

    cleaned = _URL_RE.sub(_replace, text)
    if removed:
        logger.info(f"[url-guard] removed {len(removed)} URL(s) not in whitelist: {removed}")
        # Clean-up de espaços e pontuação duplicada resultante
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = re.sub(r"\s+([.,;!?])", r"\1", cleaned)
    return cleaned


def has_scheduling_intent(user_text: str) -> bool:
    """True se a última mensagem do utilizador expressa intenção de agendamento."""
    if not user_text:
        return False
    t = user_text.lower()
    return any(k in t for k in _SCHEDULE_INTENT_KEYWORDS)


def ensure_scheduling_link(
    reply: str,
    follow_up: str,
    user_text: str,
    scheduling_link: Optional[str],
) -> tuple[str, str]:
    """Se o utilizador expressou intenção de agendamento E o agente tem um
    `scheduling_link` configurado, garante que ele aparece na resposta.
    - Se já está lá: mantém.
    - Se falta: adiciona-o no `follow_up` (ou no `reply` se follow_up estiver vazio)."""
    if not scheduling_link or not has_scheduling_intent(user_text):
        return reply, follow_up
    combined = f"{reply} {follow_up}"
    if scheduling_link in combined:
        return reply, follow_up
    # Injecta no follow_up (mais discreto que reescrever o reply)
    if not follow_up.strip():
        follow_up = f"Pode consultar horários e agendar aqui: {scheduling_link}"
    else:
        follow_up = f"{follow_up.rstrip('.')}. Aqui: {scheduling_link}"
    return reply, follow_up


# ============ Anti-repetição de perguntas já respondidas ============
_FORBIDDEN_QUESTION_PATTERNS = {
    "users": [
        r"quantos?\s+utilizadores?",
        r"quantos?\s+usuarios?",
        r"quantos?\s+colaboradores?",
        r"quantos?\s+agentes?",
        r"quantas?\s+pessoas?",
        r"tamanho\s+d[ao]\s+(?:tua|sua|vossa)?\s*equipa",
        r"sois\s+quantos?",
        r"trabalh(?:as|a)\s+sozinh[oa]",
        r"elementos?\s+n[ao]\s+equipa",
    ],
    "name": [
        r"como\s+t[eu]\s+chamas?", r"qual\s+(?:o|é|e)\s+(?:o\s+)?(?:teu|seu)\s+nome",
        r"como\s+se\s+chama",
    ],
    "email": [r"qual\s+(?:é|e)?\s*(?:o\s+)?(?:teu|seu)\s+email"],
    "phone": [r"qual\s+(?:é|e)?\s*(?:o\s+)?(?:teu|seu)\s+(?:telefone|telem[oó]vel|contacto)"],
    "sector": [
        r"em\s+que\s+setor",
        r"qual\s+(?:o|é|e)?\s*(?:o\s+)?(?:teu|seu)\s+setor",
        r"que\s+área\s+(?:é|e)",
    ],
}


def scrub_repeated_questions(reply: str, follow_up: str, facts: Dict) -> tuple[str, str]:
    """Se o LLM voltou a perguntar algo que já sabe (via facts), remove essa
    frase e força uma continuação neutra. Determinístico — corre SEMPRE
    depois do LLM.
    Returns (reply, follow_up) filtrados."""
    if not facts:
        return reply, follow_up

    def _scrub_field(text: str, field: str) -> str:
        if field not in facts:
            return text
        patterns = _FORBIDDEN_QUESTION_PATTERNS.get(field, [])
        for p in patterns:
            # Remove FRASES inteiras que contenham a pergunta proibida
            text = re.sub(
                r"[^.!?\n]*" + p + r"[^.!?\n]*[.!?\n]",
                "",
                text,
                flags=re.IGNORECASE,
            )
        return re.sub(r"\s+", " ", text).strip()

    original_reply = reply
    original_fu = follow_up
    for field in ("users", "name", "email", "phone", "sector"):
        reply = _scrub_field(reply, field)
        follow_up = _scrub_field(follow_up, field)

    if reply != original_reply or follow_up != original_fu:
        logger.info(f"[question-guard] scrubbed already-answered questions from LLM output; facts={list(facts.keys())}")

    # Se o scrub deixou o reply completamente vazio, injecta uma continuação neutra
    if not reply.strip() and follow_up.strip():
        reply = follow_up
        follow_up = ""
    elif not reply.strip():
        # Última salvaguarda — cria uma frase de continuação usando o que sabemos
        if "users" in facts:
            reply = f"Perfeito, registei — {facts['users']} utilizador{'es' if int(facts['users']) > 1 else ''}. Como posso ajudar a seguir?"
        else:
            reply = "Perfeito, registado. Como posso ajudar a seguir?"

    return reply, follow_up


# ============ Post-process principal ============
def apply_guardrails(
    reply: str,
    follow_up: str,
    facts: Dict,
    user_text: str,
    allowed_domains: Optional[List[str]] = None,
    scheduling_link: Optional[str] = None,
) -> tuple[str, str]:
    """Corre TODAS as verificações em ordem — chamado no fim de generate_response."""
    reply, follow_up = scrub_repeated_questions(reply or "", follow_up or "", facts)
    if allowed_domains:
        reply = filter_urls_by_whitelist(reply, allowed_domains, scheduling_link)
        follow_up = filter_urls_by_whitelist(follow_up, allowed_domains, scheduling_link)
    reply, follow_up = ensure_scheduling_link(reply, follow_up, user_text, scheduling_link)
    return reply, follow_up
