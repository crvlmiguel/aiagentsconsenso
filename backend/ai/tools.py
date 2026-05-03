"""Tool Execution Layer — turns orchestrator decisions into DB side-effects."""
from typing import Any, Dict, List
from datetime import datetime, timezone
import uuid


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def execute_actions(db, tenant_id: str, conversation_id: str, actions: List[Dict[str, Any]]) -> List[dict]:
    results = []
    for act in actions:
        tool = act.get("tool")
        payload = act.get("payload", {}) or {}
        if tool == "create_lead":
            doc = {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "name": payload.get("name") or "AI-Generated Lead",
                "email": payload.get("email"),
                "phone": payload.get("phone"),
                "company": payload.get("company"),
                "source": "ai",
                "stage": "new",
                "score": 50,
                "notes": payload.get("notes", ""),
                "conversation_id": conversation_id,
                "created_at": _now(),
            }
            await db.leads.insert_one(doc.copy())
            results.append({"tool": tool, "id": doc["id"], "ok": True})
        elif tool == "create_ticket":
            doc = {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "subject": payload.get("subject") or "New Ticket",
                "description": payload.get("description", ""),
                "priority": payload.get("priority", "medium"),
                "status": "open",
                "assigned_to": None,
                "conversation_id": conversation_id,
                "created_at": _now(),
            }
            await db.tickets.insert_one(doc.copy())
            results.append({"tool": tool, "id": doc["id"], "ok": True})
        else:
            results.append({"tool": tool, "ok": False, "error": "unknown_tool"})
    return results
