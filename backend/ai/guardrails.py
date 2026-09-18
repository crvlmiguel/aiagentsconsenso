"""Guardrails aplicados APÓS o LLM gerar a resposta.

Objectivos:
1. Impedir re-perguntas sobre campos já capturados (users, name, email…)
2. Filtrar URLs — apenas domínios da whitelist do agente (se definida)
3. Substituir URLs de agendamento inventados pelo link oficial do agente
4. Detectar respostas duplicadas (mesma pergunta repetida ao utilizador)
5. Enforcar linguagem neutra em género (remover "ajudá-lo", "-la", "interessado", etc.)
6. Injectar pergunta de variante PT quando o utilizador pede tradução para "português"
7. Enforcar o link oficial de agendamento (substituir qualquer scheduler inventado)
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
    facts: Optional[Dict] = None,
) -> tuple[str, str]:
    """Se o utilizador expressou intenção de agendamento (na mensagem actual OU
    via `facts.scheduling_confirmed`) E o agente tem um `scheduling_link`
    configurado, garante que ele aparece na resposta.
    - Se já está lá: mantém.
    - Se falta: adiciona-o no `follow_up` (ou no `reply` se follow_up estiver vazio)."""
    if not scheduling_link:
        return reply, follow_up
    triggered = has_scheduling_intent(user_text) or (facts or {}).get("scheduling_confirmed") == "yes"
    if not triggered:
        return reply, follow_up
    combined = f"{reply} {follow_up}"
    if scheduling_link in combined:
        return reply, follow_up
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
# --- Linguagem neutra em género ---------------------------------------------
# Substituições determinísticas na saída da IA. As chaves devem manter capitalização
# porque o sistema aplica ambos (case-sensitive) para não estragar frases começadas
# em maiúscula.
_GENDER_NEUTRAL_MAP = {
    # ajudá-lo/la
    "ajudá-lo": "ajudar",
    "ajudá-la": "ajudar",
    "ajuda-lo": "ajudar",
    "ajuda-la": "ajudar",
    "ajudá-los": "ajudar",
    "ajudá-las": "ajudar",
    # apoiá-lo/la
    "apoiá-lo": "apoiar",
    "apoiá-la": "apoiar",
    "apoia-lo": "apoiar",
    "apoia-la": "apoiar",
    "apoiá-los": "apoiar",
    "apoiá-las": "apoiar",
    # recebê-lo/la
    "recebê-lo": "receber",
    "recebê-la": "receber",
    "recebe-lo": "receber",
    "recebe-la": "receber",
    # atendê-lo
    "atendê-lo": "atender",
    "atendê-la": "atender",
    # contactá-lo/la
    "contactá-lo": "contactar",
    "contactá-la": "contactar",
    # senhor / senhora automáticos
    "o senhor": "",
    "a senhora": "",
    "caro senhor": "olá",
    "cara senhora": "olá",
    # Está interessado? → Tem interesse?
    "está interessado": "tem interesse",
    "esta interessado": "tem interesse",
    "está interessada": "tem interesse",
    "esta interessada": "tem interesse",
    # bem-vindo/a
    "seja bem-vindo": "boas-vindas",
    "seja bem-vinda": "boas-vindas",
    # obrigado por contactar-nos
    "obrigado por contactar-nos": "obrigado pelo contacto",
    "obrigada por contactar-nos": "obrigado pelo contacto",
}


def apply_gender_neutral(text: str) -> str:
    """Substitui expressões gendradas por formas neutras. Case-insensitive
    mas preserva capitalização inicial das frases."""
    if not text:
        return text
    out = text
    for k, v in _GENDER_NEUTRAL_MAP.items():
        # Case-insensitive replace preserving the first-letter case
        pattern = re.compile(re.escape(k), re.IGNORECASE)

        def _repl(m, v=v):
            match = m.group(0)
            if not v:
                return ""
            # Preserve capitalization
            if match[0].isupper():
                return v[0].upper() + v[1:]
            return v

        out = pattern.sub(_repl, out)
    # Cleanup any double spaces / stray commas produced by removals
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.,;!?])", r"\1", out)
    out = re.sub(r"([,])\s*,", r"\1", out)
    return out.strip()


# --- Enforce scheduling link (substitui links inventados) -------------------
_SCHEDULING_PATTERNS = [
    r"https?://calendly\.com/[^\s\]\)\}\>\"'`]+",
    r"https?://cal\.com/[^\s\]\)\}\>\"'`]+",
    r"https?://calendar\.google\.com/[^\s\]\)\}\>\"'`]+",
    r"https?://[^\s]*/marcar[^\s\]\)\}\>\"'`]*",
    r"https?://[^\s]*/agendar[^\s\]\)\}\>\"'`]*",
    r"https?://[^\s]*/scheduler/[^\s\]\)\}\>\"'`]*",
    r"https?://[^\s]*/agende[^\s\]\)\}\>\"'`]*",
]


def enforce_scheduling_link(text: str, scheduling_link: Optional[str]) -> str:
    """Substitui QUALQUER URL parecido com um agendador pelo link oficial do
    agente. Se scheduling_link estiver vazio, remove-os por completo (evita
    hallucination) e adiciona nota discreta."""
    if not text:
        return text
    modified = text
    replaced = False
    for pat in _SCHEDULING_PATTERNS:
        def _repl(m):
            nonlocal replaced
            url = m.group(0)
            if scheduling_link and scheduling_link in url:
                return url
            replaced = True
            return scheduling_link or ""
        modified = re.sub(pat, _repl, modified, flags=re.IGNORECASE)
    if replaced:
        logger.info(f"[scheduling-guard] replaced hallucinated scheduler with '{scheduling_link}'")
        modified = re.sub(r"\s{2,}", " ", modified).strip()
    return modified


# --- Injectar pergunta de variante PT --------------------------------------
_PT_VARIANT_QUESTION = (
    "Antes de avançar: pretende português de Portugal, português do Brasil ou outra variante?"
)


def ensure_pt_variant_question(reply: str, follow_up: str, facts: Dict) -> tuple[str, str]:
    """Se o utilizador pediu tradução para 'português' sem indicar variante,
    o guard reforça a pergunta caso a AI se tenha esquecido."""
    if facts.get("ask_pt_variant") != "yes":
        return reply, follow_up
    if facts.get("language_variant") or facts.get("pt_variant_asked") == "yes":
        return reply, follow_up
    combined_low = (reply + " " + (follow_up or "")).lower()
    already_asked = (
        "portugal" in combined_low and "brasil" in combined_low
        and ("variante" in combined_low or "outra" in combined_low or "prefere" in combined_low or "pretende" in combined_low)
    )
    if already_asked:
        return reply, follow_up
    # Injectar a pergunta ANTES do resto — é a informação crítica para desbloquear
    logger.info("[pt-variant-guard] injected variant question")
    if not reply.strip():
        reply = _PT_VARIANT_QUESTION
    else:
        reply = f"{_PT_VARIANT_QUESTION} {reply}"
    return reply, follow_up


# ============ Post-process principal ============
def apply_guardrails(
    reply: str,
    follow_up: str,
    facts: Dict,
    user_text: str,
    allowed_domains: Optional[List[str]] = None,
    scheduling_link: Optional[str] = None,
    formality: str = "informal",
) -> tuple[str, str]:
    """Corre TODAS as verificações em ordem — chamado no fim de generate_response."""
    reply, follow_up = scrub_repeated_questions(reply or "", follow_up or "", facts)
    reply, follow_up = ensure_pt_variant_question(reply, follow_up, facts)
    # Linguagem neutra em género — aplicar sempre (formal ou informal)
    reply = apply_gender_neutral(reply)
    follow_up = apply_gender_neutral(follow_up)
    # Enforce scheduling link antes do whitelist (pode substituir por scheduling_link)
    reply = enforce_scheduling_link(reply, scheduling_link)
    follow_up = enforce_scheduling_link(follow_up, scheduling_link)
    if allowed_domains:
        reply = filter_urls_by_whitelist(reply, allowed_domains, scheduling_link)
        follow_up = filter_urls_by_whitelist(follow_up, allowed_domains, scheduling_link)
    reply, follow_up = ensure_scheduling_link(reply, follow_up, user_text, scheduling_link, facts=facts)
    return reply, follow_up
