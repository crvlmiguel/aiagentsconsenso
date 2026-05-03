"""Intent Engine — classifies user messages."""
from .router import llm_complete, extract_json

INTENT_SYSTEM = """You are an intent classification engine for a business AI OS.
Your job: classify the user's message and respond with a single JSON object only.

Schema (strict):
{
  "intent": "sales_inquiry" | "support_request" | "complaint" | "booking" | "information" | "pricing" | "greeting" | "feedback" | "other",
  "category": "sales" | "support" | "billing" | "technical" | "general",
  "urgency": "low" | "medium" | "high" | "urgent",
  "confidence": 0.0 to 1.0
}

Return JSON only. No prose."""


async def classify_intent(text: str, session_id: str, api_provider: str = "emergent", api_key: str = "") -> dict:
    out = await llm_complete(
        system_message=INTENT_SYSTEM,
        user_text=f"Message: {text}",
        session_id=f"intent-{session_id}",
        task="fast",
        api_provider=api_provider,
        api_key=api_key,
    )
    data = extract_json(out)
    return {
        "intent": data.get("intent", "other"),
        "category": data.get("category", "general"),
        "urgency": data.get("urgency", "medium"),
        "confidence": float(data.get("confidence", 0.5) or 0.5),
    }
