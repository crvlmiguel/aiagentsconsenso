"""Backfill: corre a qualificação CRM em todas as conversas existentes
que ainda não tenham `qualification`. Útil para a UI mostrar dados imediatamente
após adicionar o sistema de CRM panel."""
import os
import asyncio
import sys
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
load_dotenv(Path(__file__).parent / ".env")

from ai.qualify import qualify_conversation
from datetime import datetime, timezone


def now_iso():
    return datetime.now(timezone.utc).isoformat()


MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


async def run(force: bool = False):
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    query = {} if force else {"qualification": {"$exists": False}}
    convos = await db.conversations.find(query, {"_id": 0}).to_list(500)
    print(f"A processar {len(convos)} conversas (force={force})…")
    ok = 0
    for c in convos:
        msgs = await db.messages.find({"conversation_id": c["id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
        if not msgs:
            continue
        agent = await db.agents.find_one({"id": c.get("agent_id")}, {"_id": 0}) if c.get("agent_id") else None
        ap = (agent or {}).get("api_provider", "emergent")
        ak = (agent or {}).get("api_key", "")
        try:
            q = await qualify_conversation(msgs, c["id"], ap, ak)
            q["updated_at"] = now_iso()
            await db.conversations.update_one(
                {"id": c["id"]},
                {"$set": {"qualification": q, "tags": q.get("tags", [])}},
            )
            ok += 1
            print(f"  ✓ {c['contact_name']:24} → {q['status']:18} | tags={q.get('tags')}")
        except Exception as e:
            print(f"  ✗ {c.get('contact_name', '?'):24} falhou: {e}")
    print(f"OK: {ok}/{len(convos)}")
    client.close()


if __name__ == "__main__":
    force = "--force" in sys.argv
    asyncio.run(run(force=force))
