"""Tradução de campos de agente entre 6 idiomas suportados.

Usa `llm_complete` (Emergent Universal Key → gpt-4o-mini por defeito).
Preserva formatação, markdown, URLs, variáveis ({user_name}), placeholders e
emojis. NUNCA resume nem reinterpreta o conteúdo.
"""
import asyncio
import logging
import uuid
from typing import Dict, List, Optional

from .router import llm_complete

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {
    "pt": "Português Europeu (pt-PT)",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
    "ca": "Català",
}


_TRANSLATION_SYSTEM = """You are a professional translator for SaaS chatbot
configurations. You translate content to the target language while preserving:
- All formatting (markdown bold, italics, lists, line breaks, headings)
- All variables and placeholders (e.g. {user_name}, {{ field }}, %s, $1)
- All URLs, email addresses and phone numbers (DO NOT translate or alter them)
- All HTML/JSX tags and attributes
- All emojis (keep at the same position)
- All proper nouns: brand names (Consenso Plus, ImmoAI, Maria, StayLocal, Abby, ABBI),
  product names, location names, company names — keep as-is
- All technical commands and identifiers in `backticks`
- All prices (€49,90), currencies, percentages and numbers
- The original tone (formal/informal — keep "tu" treatment if Portuguese source uses it,
  pick the closest informal "you" equivalent in target language)

You DO translate:
- All natural language sentences and paragraphs
- All labels, descriptions, icebreakers, button captions
- All user-facing messages

CRITICAL RULES:
1. NEVER summarize. Translate the ENTIRE text.
2. NEVER add explanations, prefaces, or comments. Output ONLY the translation.
3. NEVER change the meaning, structure or order of sentences.
4. NEVER omit content because you think it's redundant.
5. If a section is already in the target language, copy it verbatim.
6. For Portuguese target, ALWAYS use European Portuguese (pt-PT), NEVER Brazilian.
"""


def _user_prompt(text: str, target_lang_code: str) -> str:
    target_label = SUPPORTED_LANGUAGES.get(target_lang_code, target_lang_code)
    return (
        f"Translate the following content to {target_label} ({target_lang_code}). "
        f"Output ONLY the translation, no preface, no comments, no quotes.\n\n"
        f"=== CONTENT START ===\n{text}\n=== CONTENT END ==="
    )


async def translate_text(
    text: str,
    target_lang: str,
    source_lang: Optional[str] = None,
    api_provider: str = "emergent",
    api_key: Optional[str] = None,
) -> str:
    """Translate a single piece of text. Returns the translated text.
    Empty/short inputs are returned as-is.
    Force-uses Emergent key (ignores agent BYO keys to avoid platform feature
    breaking due to invalid/expired user keys)."""
    if not text or not isinstance(text, str):
        return text or ""
    if target_lang == source_lang:
        return text
    stripped = text.strip()
    if len(stripped) < 2:
        return text  # nothing meaningful to translate
    if target_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Idioma de destino não suportado: {target_lang}")

    session = f"translate-{uuid.uuid4().hex[:12]}"
    last_err: Optional[Exception] = None
    # 1 retry with backoff on transient LLM failures (rate-limit / 5xx)
    for attempt in range(2):
        try:
            out = await llm_complete(
                system_message=_TRANSLATION_SYSTEM,
                user_text=_user_prompt(text, target_lang),
                session_id=session,
                task="fast",
                api_provider="emergent",   # always platform key for internal feature
                api_key=None,
            )
            cleaned = (out or "").strip()
            # Strip occasional wrapping quotes the model may add
            if cleaned.startswith('"') and cleaned.endswith('"') and cleaned.count('"') == 2:
                cleaned = cleaned[1:-1]
            return cleaned or text
        except Exception as e:
            last_err = e
            logger.warning(f"translate_text attempt {attempt+1} failed ({target_lang}): {e}")
            if attempt == 0:
                await asyncio.sleep(1.2)  # brief backoff before retry
    # Both attempts failed — re-raise so caller endpoint surfaces an honest error
    raise RuntimeError(f"LLM falhou após 2 tentativas: {str(last_err)[:200]}")


# Campos do agente que devem ser traduzidos.
# Listas (icebreakers) são traduzidas item-a-item.
TRANSLATABLE_TEXT_FIELDS = (
    "name",
    "welcome_message",
    "tone",
    "goal",
    "system_prompt",
    "rules",
    "knowledge",
)
TRANSLATABLE_LIST_FIELDS = (
    "icebreakers",
)

# Campos a NUNCA traduzir
PRESERVED_FIELDS = (
    "id", "tenant_id", "api_key", "api_provider",
    "model_provider", "model_name",
    "channels", "email", "data_source_ids", "tools",
    "theme", "avatar_url",
    "created_at", "updated_at",
    "is_customized",
)


async def translate_agent_payload(
    agent: Dict, target_lang: str, source_lang: Optional[str] = None,
    api_provider: str = "emergent", api_key: Optional[str] = None,
) -> Dict:
    """Returns a NEW dict with translated fields. Preserved fields are kept verbatim.
    `default_language` is updated to the target language.
    Resilient: if a single field translation fails, keeps the original (logged warning).
    Only raises if the LLM is fundamentally broken (e.g. no API key, all fields fail)."""
    if target_lang not in SUPPORTED_LANGUAGES:
        raise ValueError(f"Idioma de destino não suportado: {target_lang}")

    out = dict(agent)  # shallow copy
    src = source_lang or agent.get("default_language") or "pt"
    if target_lang == src:
        out["default_language"] = target_lang
        return out

    # Translate each text field in parallel for speed
    text_field_names: List[str] = [
        f for f in TRANSLATABLE_TEXT_FIELDS if (out.get(f) or "").strip()
    ]
    text_tasks = [
        translate_text(out.get(f) or "", target_lang, src, api_provider, api_key)
        for f in text_field_names
    ]
    # List fields — translate each item
    list_tasks: Dict[str, List] = {}
    for lf in TRANSLATABLE_LIST_FIELDS:
        items = out.get(lf) or []
        list_tasks[lf] = [
            translate_text(item or "", target_lang, src, api_provider, api_key)
            for item in items
        ]

    # Execute all translations in parallel
    text_results: List = []
    if text_tasks:
        text_results = await asyncio.gather(*text_tasks, return_exceptions=True)
    list_results: Dict[str, List] = {}
    for lf, tasks in list_tasks.items():
        if tasks:
            list_results[lf] = await asyncio.gather(*tasks, return_exceptions=True)

    # Count failures
    total_attempts = len(text_results) + sum(len(v) for v in list_results.values())
    total_failures = 0

    for field, result in zip(text_field_names, text_results):
        if isinstance(result, Exception):
            logger.warning(f"[translate] field '{field}' failed: {result} — keeping original")
            total_failures += 1
            # leave out[field] as the original value (already in `out`)
        else:
            out[field] = result

    for lf, results in list_results.items():
        merged = []
        original_items = out.get(lf) or []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"[translate] {lf}[{i}] failed: {result} — keeping original")
                total_failures += 1
                merged.append(original_items[i] if i < len(original_items) else "")
            else:
                merged.append(result)
        out[lf] = merged

    # If everything failed → raise (LLM is fundamentally broken)
    if total_attempts > 0 and total_failures == total_attempts:
        raise RuntimeError(
            "Tradução falhou em todos os campos. "
            "Verifica se a Emergent LLM Key está válida e com créditos."
        )

    out["default_language"] = target_lang
    return out
