"""Migração one-shot: renomeia emails de admins do domínio antigo
(consenso.plus / consensoplus.com) para consenso-agents.com.
Idempotente."""
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

MIGRATIONS = [
    ("demo@consenso.plus", "demo@consenso-agents.com"),
    ("admin@consensoplus.com", "admin@consenso-agents.com"),
]


async def run():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    for old, new in MIGRATIONS:
        existing_new = await db.users.find_one({"email": new}, {"_id": 0})
        existing_old = await db.users.find_one({"email": old}, {"_id": 0})
        if existing_new and not existing_old:
            print(f"OK · {new} já existe, nada a fazer.")
            continue
        if existing_old and existing_new:
            # Both exist — keep the new one, remove the old (preserve canonical)
            await db.users.delete_one({"email": old})
            print(f"DUP · removido {old} (já existia {new}).")
            continue
        if existing_old and not existing_new:
            res = await db.users.update_one({"email": old}, {"$set": {"email": new}})
            print(f"MIG · {old} → {new} (matched={res.matched_count}, mod={res.modified_count}).")
            continue
        print(f"-- · nem {old} nem {new} encontrados.")
    client.close()


if __name__ == "__main__":
    asyncio.run(run())
