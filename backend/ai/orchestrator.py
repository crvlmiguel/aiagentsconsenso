"""Agent Orchestrator — decides what actions to take and generates responses."""
from typing import List, Dict, Any
from .router import llm_complete


def decide_actions(intent: dict, structure: dict, agent: dict) -> Dict[str, Any]:
    """Rules-based orchestration using intent + structure + agent tool config."""
    enabled_tools = {t["key"] for t in agent.get("tools", []) if t.get("enabled")}
    actions: List[Dict[str, Any]] = []

    domain = structure.get("domain", "general")
    typ = structure.get("type", "inquiry")
    priority = structure.get("priority", "medium")
    entities = structure.get("entities", {}) or {}

    # Lead creation path
    if typ == "lead" or domain == "sales" or intent.get("intent") in {"sales_inquiry", "pricing", "booking"}:
        if "create_lead" in enabled_tools:
            actions.append({
                "tool": "create_lead",
                "payload": {
                    "name": entities.get("name") or structure.get("business_context", "New Lead")[:60],
                    "email": entities.get("email"),
                    "phone": entities.get("phone"),
                    "company": entities.get("company"),
                    "notes": structure.get("business_context", ""),
                },
            })

    # Ticket creation path
    if typ == "ticket" or domain == "support" or intent.get("intent") in {"support_request", "complaint"}:
        if "create_ticket" in enabled_tools:
            actions.append({
                "tool": "create_ticket",
                "payload": {
                    "subject": (structure.get("business_context") or intent.get("intent", "Support"))[:80],
                    "description": structure.get("business_context", ""),
                    "priority": priority if priority != "urgent" else "urgent",
                },
            })

    response_mode = "reply"
    if priority in {"urgent", "high"} and intent.get("intent") == "complaint":
        response_mode = "reply_and_notify"

    return {"actions": actions, "response_mode": response_mode}


async def generate_response(agent: dict, history: list, intent: dict, structure: dict, session_id: str) -> str:
    """Compose the final assistant reply respecting agent tone & rules."""
    tone = agent.get("tone", "professional")
    rules = agent.get("rules", "")
    knowledge = agent.get("knowledge", "")
    base_prompt = agent.get("system_prompt") or "You are a helpful AI assistant."

    system = f"""{base_prompt}

Tone: {tone}.
Goal: {agent.get('goal', 'Help the customer')}.
Rules: {rules or 'Be concise. Be honest. Offer to connect a human for complex requests.'}

Business knowledge you can rely on:
{knowledge or '(no extra knowledge base configured)'}

You already classified the latest user message as:
- Intent: {intent.get('intent')} | Category: {intent.get('category')} | Urgency: {intent.get('urgency')}
- Structured type: {structure.get('type')} | Domain: {structure.get('domain')} | Priority: {structure.get('priority')}
- Needs: {', '.join(structure.get('needs', [])) or 'n/a'}

Respond in 1-3 short paragraphs. Be helpful, natural, never mention this internal JSON."""

    # Compose last N turns
    turns = []
    for m in history[-10:]:
        role = "USER" if m["sender"] == "user" else "ASSISTANT"
        turns.append(f"{role}: {m['text']}")
    convo = "\n".join(turns) if turns else "(new conversation)"

    provider = agent.get("model_provider") or "auto"
    model = agent.get("model_name") or "gpt-5.1"

    return await llm_complete(
        system_message=system,
        user_text=f"Conversation so far:\n{convo}\n\nReply to the latest user message.",
        session_id=f"reply-{session_id}",
        task="reasoning" if intent.get("urgency") in {"high", "urgent"} else "fast",
        provider=provider if provider != "auto" else None,
        model=model if provider != "auto" else None,
    )
