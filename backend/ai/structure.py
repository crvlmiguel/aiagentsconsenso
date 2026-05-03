"""Structure Engine — turns language into a structured business object."""
from .router import llm_complete, extract_json

STRUCTURE_SYSTEM = """You are the Structure Engine of a business AI OS.
Transform the user's natural language message into a structured business object.

Schema (strict, JSON only):
{
  "type": "lead" | "ticket" | "inquiry" | "conversation",
  "domain": "sales" | "support" | "billing" | "operations" | "general",
  "channels": ["web" | "whatsapp" | "instagram" | "telegram" | "messenger" | "email"],
  "needs": [ "short phrase", ... ],
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

Return JSON only. No prose."""


async def structure_message(text: str, channel: str, session_id: str) -> dict:
    out = await llm_complete(
        system_message=STRUCTURE_SYSTEM,
        user_text=f"Channel: {channel}\nMessage: {text}",
        session_id=f"structure-{session_id}",
        task="reasoning",
    )
    data = extract_json(out)
    return {
        "type": data.get("type", "inquiry"),
        "domain": data.get("domain", "general"),
        "channels": data.get("channels", [channel]),
        "needs": data.get("needs", []),
        "priority": data.get("priority", "medium"),
        "entities": data.get("entities", {}),
        "business_context": data.get("business_context", ""),
    }
