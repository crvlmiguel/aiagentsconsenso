"""Multi-LLM router using emergentintegrations library.
Routes tasks to different providers. Supports per-agent BYO keys OR Emergent Universal Key.
"""
import os
import json
import logging
import re
from typing import Optional, AsyncIterator

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# Model strategy — optimized for SPEED (3-5s response target).
# gpt-4o-mini is OpenAI's fastest model, ~1-2s typical, comparable quality to flash.
TASK_MODELS = {
    "reasoning": ("openai", "gpt-4o-mini"),
    "long_context": ("openai", "gpt-4o-mini"),
    "fast": ("openai", "gpt-4o-mini"),
    "fallback": ("openai", "gpt-4o-mini"),
}


class LLMConfigMissing(Exception):
    """Raised when the agent is not configured with a usable API key."""


class LLMProviderError(Exception):
    """Raised when the provider call actually fails (network / quota / 5xx)."""


def pick_model(task: str = "fast") -> tuple[str, str]:
    return TASK_MODELS.get(task, TASK_MODELS["fallback"])


def _resolve_key(api_provider: str, api_key: Optional[str]) -> str:
    """Key priority:
    1. If agent has explicit api_key set → use it (BYO key per agent).
    2. If api_provider is 'openai' and OPENAI_API_KEY env is set → use direct OpenAI.
    3. Else fall back to Emergent Universal Key.
    """
    if api_key:
        return api_key
    openai_env = os.environ.get("OPENAI_API_KEY", "") or OPENAI_KEY
    if api_provider == "openai" and openai_env:
        return openai_env
    emergent = os.environ.get("EMERGENT_LLM_KEY", "") or EMERGENT_KEY
    if not emergent:
        raise LLMConfigMissing("API da IA não configurada ou inválida.")
    return emergent


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
            raise LLMProviderError(f"API da IA não configurada ou inválida. Detalhe: {str(e2)[:160]}") from e2


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


async def llm_stream(
    system_message: str,
    user_text: str,
    api_provider: str = "openai",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
) -> AsyncIterator[str]:
    """Stream raw text chunks from an OpenAI-compatible model.

    Currently only supports OpenAI (which is what our default `gpt-4o-mini` route uses).
    Falls back gracefully — caller should catch LLMConfigMissing / LLMProviderError
    and degrade to non-streaming llm_complete().
    """
    key = _resolve_key(api_provider, api_key)
    mdl = model or pick_model("fast")[1]
    try:
        import openai
        client = openai.AsyncOpenAI(api_key=key, timeout=20.0)
        stream = await client.chat.completions.create(
            model=mdl,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_text},
            ],
            stream=True,
            temperature=0.7,
        )
        async for ev in stream:
            try:
                delta = ev.choices[0].delta.content if ev.choices else None
            except Exception:
                delta = None
            if delta:
                yield delta
    except Exception as e:
        raise LLMProviderError(f"Streaming falhou: {str(e)[:160]}") from e
