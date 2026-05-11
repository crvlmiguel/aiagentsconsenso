"""Unified message analysis — combines intent classification + structure extraction
in a SINGLE LLM call (saves ~2-3 seconds vs running them sequentially or in parallel).

Returns the same shape as the legacy `classify_intent` + `structure_message` combined.
"""
import re

from .router import llm_complete, extract_json

ANALYZE_SYSTEM = """You are a fast message analyzer for a business AI OS.
For the user's message, return ONE JSON object with intent classification AND
structured extraction. Output JSON ONLY, no prose, no markdown.

Schema (strict):
{
  "intent": "sales_inquiry" | "support_request" | "complaint" | "booking" | "information" | "pricing" | "greeting" | "feedback" | "other",
  "category": "sales" | "support" | "billing" | "technical" | "general",
  "urgency": "low" | "medium" | "high" | "urgent",
  "confidence": 0.0,
  "type": "lead" | "ticket" | "inquiry" | "conversation",
  "domain": "sales" | "support" | "billing" | "operations" | "general",
  "needs": ["short phrase", ...],
  "priority": "low" | "medium" | "high" | "urgent",
  "entities": {
    "name": string|null,
    "email": string|null,
    "phone": string|null,
    "company": string|null,
    "product": string|null,
    "amount": string|null,
    "date": string|null
  },
  "business_context": "1-sentence summary"
}

Be FAST. Be CONCISE. JSON only."""


# ---- Fast-path heuristics ----------------------------------------------------
# Quickly classify trivial messages WITHOUT calling an LLM. Saves ~2 seconds
# on gpt-4o-mini for very common messages (greetings, icebreakers, conversational
# turns, real-estate queries). The LLM analyze step is only useful for rich, long
# messages that contain explicit lead intent + entities — for everything else,
# regex extraction is more than enough.

_GREETING_RE = re.compile(
    r"^\s*(ol[áa]|hello|hi|hey|hola|bonjour|buongiorno|salut|hallo|bom dia|boa tarde|boa noite|good (?:morning|afternoon|evening))[!.?\s]*$",
    re.IGNORECASE,
)
_REAL_ESTATE_KEYWORDS = re.compile(
    r"\b(t1|t2|t3|t4|t5|v1|v2|v3|v4|v5|moradia|apartamento|im[óo]vel|im[óo]veis|"
    r"comprar|arrendar|investimento|investir|cr[ée]dito|presta[çc][ãa]o|"
    r"casa|fl[áa]t|loft|estudio|vivenda)\b",
    re.IGNORECASE,
)
_COMPLAINT_KEYWORDS = re.compile(
    r"\b(reclama[çc][ãa]o|reclamar|urgente|emerg[êe]ncia|problema grave|n[ãa]o funciona|"
    r"complaint|urgent|emergency|broken|not working|terrible|awful|p[ée]ssimo)\b",
    re.IGNORECASE,
)
_SUPPORT_KEYWORDS = re.compile(
    r"\b(ajuda|help|suporte|support|d[úu]vida|problema|issue|erro|error|"
    r"como (?:fa[çc]o|posso|funciona)|how (?:to|do|can))\b",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\d{2,3}[\s.-]?){2,4}\d{2,4}\b")


def _quick_extract(text: str) -> dict:
    return {
        "name": None,
        "email": (EMAIL_RE.search(text) or [None])[0] if EMAIL_RE.search(text) else None,
        "phone": (PHONE_RE.search(text).group(0) if PHONE_RE.search(text) else None),
        "company": None,
        "product": None,
        "amount": None,
        "date": None,
    }


def _fast_path(text: str, channel: str) -> tuple[dict, dict] | None:
    """Returns (intent, structure) tuple if we can classify confidently without an LLM,
    else None (caller should fall back to the LLM-powered analyze_message).

    Strategy: be GREEDY. Only fall back to the LLM for genuinely ambiguous cases
    (long-ish messages without any signal). For everything else we use regex
    classification which is good enough for the routing decisions in `decide_actions`."""
    t = (text or "").strip()
    if not t:
        return None

    ents = _quick_extract(t)
    has_estate = bool(_REAL_ESTATE_KEYWORDS.search(t))
    has_complaint = bool(_COMPLAINT_KEYWORDS.search(t))
    has_support = bool(_SUPPORT_KEYWORDS.search(t))
    has_contact = bool(ents["email"] or ents["phone"])

    # 1) Greeting / very short — always conversational
    if _GREETING_RE.match(t) or len(t) < 6:
        return (
            {"intent": "greeting", "category": "general", "urgency": "low", "confidence": 0.95},
            {"type": "conversation", "domain": "general", "channels": [channel],
             "needs": [], "priority": "low", "entities": ents,
             "business_context": t[:60]},
        )

    # 2) Complaint / urgent — escalate priority, mark as ticket
    if has_complaint:
        return (
            {"intent": "complaint", "category": "support", "urgency": "high", "confidence": 0.85},
            {"type": "ticket", "domain": "support", "channels": [channel],
             "needs": [t[:80]], "priority": "high", "entities": ents,
             "business_context": t[:120]},
        )

    # 3) Real-estate query → sales lead (works for ABBI / property agents)
    if has_estate:
        return (
            {"intent": "sales_inquiry", "category": "sales", "urgency": "medium", "confidence": 0.9},
            {"type": "lead", "domain": "sales", "channels": [channel],
             "needs": [t[:80]], "priority": "medium", "entities": ents,
             "business_context": t[:120]},
        )

    # 4) Explicit support / help intent — ticket / inquiry
    if has_support:
        return (
            {"intent": "support_request", "category": "support", "urgency": "medium", "confidence": 0.8},
            {"type": "inquiry", "domain": "support", "channels": [channel],
             "needs": [t[:80]], "priority": "medium", "entities": ents,
             "business_context": t[:120]},
        )

    # 5) Short conversational turn (< 200 chars) without complaint/estate/support
    #    keywords — treat as a generic inquiry. If the user provided contact info
    #    (email/phone) we mark it as a lead so create_lead can still fire.
    if len(t) < 200:
        return (
            {"intent": ("sales_inquiry" if has_contact else "information"),
             "category": "general", "urgency": "low",
             "confidence": 0.75 if has_contact else 0.7},
            {"type": ("lead" if has_contact else "inquiry"),
             "domain": "general", "channels": [channel],
             "needs": [t[:80]], "priority": "low", "entities": ents,
             "business_context": t[:120]},
        )

    # Long messages (>= 200 chars) — let the LLM analyze for nuanced classification.
    return None


async def analyze_message(
    text: str,
    channel: str,
    session_id: str,
    api_provider: str = "emergent",
    api_key: str = "",
) -> tuple[dict, dict]:
    """Single LLM call returning (intent_dict, structure_dict).
    Both dicts have the same shape as the legacy classify_intent/structure_message.
    Fast-paths trivial cases (greetings, real-estate queries) without calling the LLM."""

    fast = _fast_path(text, channel)
    if fast is not None:
        return fast

    out = await llm_complete(
        system_message=ANALYZE_SYSTEM,
        user_text=f"Channel: {channel}\nMessage: {text}",
        session_id=f"analyze-{session_id}",
        task="fast",
        api_provider=api_provider,
        api_key=api_key,
    )
    data = extract_json(out) or {}

    intent = {
        "intent": data.get("intent", "other"),
        "category": data.get("category", "general"),
        "urgency": data.get("urgency", "medium"),
        "confidence": float(data.get("confidence", 0.5) or 0.5),
    }
    structure = {
        "type": data.get("type", "inquiry"),
        "domain": data.get("domain", "general"),
        "channels": [channel],
        "needs": data.get("needs", []) if isinstance(data.get("needs"), list) else [],
        "priority": data.get("priority", "medium"),
        "entities": data.get("entities", {}) if isinstance(data.get("entities"), dict) else {},
        "business_context": data.get("business_context", ""),
    }
    return intent, structure
