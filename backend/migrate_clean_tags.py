"""Limpa tags genéricas legadas de todas as conversas e leads.
Tags banidas: 'sales', 'general', 'support', 'billing', 'technical', 'other',
'sales_inquiry', 'support_request', 'complaint', 'booking', 'information',
'pricing', 'greeting', 'feedback', 'high', 'urgent' (estado movido para qualification).
Idempotente."""
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

BANNED = {
    "sales", "general", "support", "billing", "technical", "other",
    "sales_inquiry", "support_request", "complaint", "booking",
    "information", "pricing", "greeting", "feedback",
    "high", "urgent", "low", "medium",
}


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    cleaned_convos = 0
    async for c in db.conversations.find({}, {"_id": 0, "id": 1, "tags": 1}):
        tags = c.get("tags") or []
        new_tags = [t for t in tags if isinstance(t, str) and t.strip().lower() not in BANNED]
        if len(new_tags) != len(tags):
            await db.conversations.update_one({"id": c["id"]}, {"$set": {"tags": new_tags}})
            cleaned_convos += 1
    print(f"Conversas limpas: {cleaned_convos}")

    cleaned_leads = 0
    async for l in db.leads.find({}, {"_id": 0, "id": 1, "tags": 1}):
        tags = l.get("tags") or []
        new_tags = [t for t in tags if isinstance(t, str) and t.strip().lower() not in BANNED]
        if len(new_tags) != len(tags):
            await db.leads.update_one({"id": l["id"]}, {"$set": {"tags": new_tags}})
            cleaned_leads += 1
    print(f"Leads limpos: {cleaned_leads}")

    client.close()


if __name__ == "__main__":
    asyncio.run(run())
