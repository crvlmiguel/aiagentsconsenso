"""Multi-LLM router using emergentintegrations library.
Routes tasks to different providers. Supports per-agent BYO keys OR Emergent Universal Key.
"""
import os
import json
import logging
import re
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

TASK_MODELS = {
    "reasoning": ("openai", "gpt-5.1"),
    "long_context": ("anthropic", "claude-sonnet-4-5-20250929"),
    "fast": ("gemini", "gemini-2.5-flash"),
    "fallback": ("openai", "gpt-5.1"),
}


class LLMConfigMissing(Exception):
    """Raised when the agent is not configured with a usable API key."""


class LLMProviderError(Exception):
    """Raised when the provider call actually fails (network / quota / 5xx)."""


def pick_model(task: str = "fast") -> tuple[str, str]:
    return TASK_MODELS.get(task, TASK_MODELS["fallback"])


def _resolve_key(api_provider: str, api_key: Optional[str]) -> str:
    """If api_provider is emergent/auto OR key is empty, use Emergent Universal Key."""
    emergent = os.environ.get("EMERGENT_LLM_KEY", "") or EMERGENT_KEY
    if api_provider in ("emergent", "auto", "", None) or not api_key:
        if not emergent:
            raise LLMConfigMissing(
                "Não foi encontrada a chave de IA. Configure uma chave própria no agente "
                "ou contacte o administrador para ativar a Chave Universal Emergent."
            )
        return emergent
    return api_key


async def llm_complete(
    system_message: str,
    user_text: str,
    session_id: str,
    task: str = "fast",
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_provider: str = "emergent",
    api_key: Optional[str] = None,
) -> str:
    """Send a message, return the raw assistant text. Raises LLMConfigMissing / LLMProviderError."""
    # Choose model
    if provider and model and provider != "auto":
        prov, mdl = provider, model
    else:
        prov, mdl = pick_model(task)

    # If user BYO key, respect their provider choice
    if api_provider and api_provider not in ("emergent", "auto") and api_key:
        prov = api_provider
        if model:
            mdl = model

    key = _resolve_key(api_provider, api_key)

    chat = LlmChat(
        api_key=key, session_id=session_id, system_message=system_message,
    ).with_model(prov, mdl)

    try:
        resp = await chat.send_message(UserMessage(text=user_text))
        return str(resp)
    except Exception as e:
        logger.warning(f"LLM {prov}/{mdl} failed: {e}. Trying fallback.")
        try:
            prov2, mdl2 = pick_model("fallback")
            chat2 = LlmChat(
                api_key=key, session_id=session_id, system_message=system_message,
            ).with_model(prov2, mdl2)
            resp = await chat2.send_message(UserMessage(text=user_text))
            return str(resp)
        except Exception as e2:
            raise LLMProviderError(f"Falha ao contactar o provider de IA ({prov}/{mdl}): {e2}") from e2


async def test_connection(api_provider: str, api_key: Optional[str], model: Optional[str] = None) -> dict:
    """Small ping to verify the configured key works. Returns {ok, provider, model, error?}."""
    try:
        key = _resolve_key(api_provider, api_key)
    except LLMConfigMissing as e:
        return {"ok": False, "error": str(e), "code": "config_missing"}

    # For emergent/auto, use a safe default; for BYO, trust the pair
    if api_provider not in ("emergent", "auto") and api_key:
        prov = api_provider
        defaults = {"openai": "gpt-5.1", "anthropic": "claude-sonnet-4-5-20250929", "gemini": "gemini-2.5-flash"}
        mdl = model if model else defaults.get(prov, "gpt-5.1")
    else:
        prov = "gemini"
        mdl = "gemini-2.5-flash"

    try:
        chat = LlmChat(api_key=key, session_id="test-conn", system_message="Responde com uma palavra: OK").with_model(prov, mdl)
        resp = await chat.send_message(UserMessage(text="ping"))
        return {"ok": True, "provider": prov, "model": mdl, "sample": str(resp)[:80]}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], "code": "provider_error", "provider": prov, "model": mdl}


def extract_json(text: str) -> dict:
    if not text:
        return {}
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        cleaned = match.group(0)
    try:
        return json.loads(cleaned)
    except Exception:
        return {}
