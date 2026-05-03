"""Multi-LLM router using emergentintegrations library.

Routes tasks to different providers:
- complex reasoning  -> OpenAI GPT
- long context       -> Anthropic Claude
- fast / simple      -> Google Gemini
- fallback           -> OpenAI GPT
"""
import os
import json
import logging
import re
from typing import Optional

from emergentintegrations.llm.chat import LlmChat, UserMessage

logger = logging.getLogger(__name__)

EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

# Default model registry per task
TASK_MODELS = {
    "reasoning": ("openai", "gpt-5.1"),
    "long_context": ("anthropic", "claude-sonnet-4-5-20250929"),
    "fast": ("gemini", "gemini-2.5-flash"),
    "fallback": ("openai", "gpt-5.1"),
}


def pick_model(task: str = "fast") -> tuple[str, str]:
    return TASK_MODELS.get(task, TASK_MODELS["fallback"])


async def llm_complete(
    system_message: str,
    user_text: str,
    session_id: str,
    task: str = "fast",
    provider: Optional[str] = None,
    model: Optional[str] = None,
) -> str:
    """Send a message, return the raw assistant text."""
    if provider and model and provider != "auto":
        prov, mdl = provider, model
    else:
        prov, mdl = pick_model(task)

    chat = LlmChat(
        api_key=EMERGENT_KEY,
        session_id=session_id,
        system_message=system_message,
    ).with_model(prov, mdl)

    try:
        resp = await chat.send_message(UserMessage(text=user_text))
        return str(resp)
    except Exception as e:
        logger.warning(f"LLM {prov}/{mdl} failed: {e}. Falling back.")
        try:
            prov2, mdl2 = pick_model("fallback")
            chat2 = LlmChat(
                api_key=EMERGENT_KEY,
                session_id=session_id,
                system_message=system_message,
            ).with_model(prov2, mdl2)
            resp = await chat2.send_message(UserMessage(text=user_text))
            return str(resp)
        except Exception as e2:
            logger.error(f"Fallback LLM also failed: {e2}")
            return "I'm having trouble reaching the AI service right now. A team member will follow up shortly."


def extract_json(text: str) -> dict:
    """Best-effort JSON extraction from LLM output."""
    if not text:
        return {}
    # Remove code fences
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)
    # Find first { ... } block
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        cleaned = match.group(0)
    try:
        return json.loads(cleaned)
    except Exception:
        return {}
