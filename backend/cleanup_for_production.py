"""Production cleanup: remove demo/test tenants and fixture data, keep real assets.

KEEPS:
- Tenant of `admin@consenso-agents.com` (renamed from "Imobiliária Lisboa" → "Consenso")
- Agent "Abby — ABBI Imóveis" + its 9 real properties data source
- Tenant of `cevlmiguel@gmail.com` (real user signup)

REMOVES:
- All TEST_*, TestCo_*, "Imobiliária Lisboa" duplicates
- The placeholder `demo@consenso-agents.com` account ("A minha empresa")
- Duplicate "Aria" agent inside the admin tenant (was a legacy seed)
- ALL conversations, leads, messages from the admin tenant (fictional Bench/FinalTest/Tester)
- Orphaned data sources, channels, integrations, qualifications, etc.

Idempotent — can be safely re-run.
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

KEEP_USER_EMAILS = {
    "admin@consenso-agents.com",
    "cevlmiguel@gmail.com",
}
KEEP_AGENT_NAME_SUBSTRINGS = ["Abby"]  # case-insensitive
NEW_TENANT_NAME = "Consenso"


async def run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # Step 1 — find tenant_ids to KEEP (those owning by users we keep)
    keep_tenant_ids = set()
    async for u in db.users.find(
        {"email": {"$in": list(KEEP_USER_EMAILS)}}, {"_id": 0}
    ):
        keep_tenant_ids.add(u["tenant_id"])
    print(f"KEEP tenants: {len(keep_tenant_ids)} → {keep_tenant_ids}")

    # Step 2 — find tenants to DELETE
    all_tenant_ids = set()
    async for t in db.tenants.find({}, {"_id": 0, "id": 1}):
        all_tenant_ids.add(t["id"])
    delete_tenant_ids = all_tenant_ids - keep_tenant_ids
    print(f"DELETE tenants: {len(delete_tenant_ids)}")

    # Step 3 — wipe all collections scoped by tenant_id for deleted tenants
    SCOPED_COLLECTIONS = [
        "users", "agents", "conversations", "messages", "leads", "tickets",
        "data_sources", "data_chunks", "channels", "integrations",
        "team_invites", "audit_logs", "icebreakers", "memberships",
        "metrics", "events", "qualifications",
    ]
    for coll in SCOPED_COLLECTIONS:
        if coll not in await db.list_collection_names():
            continue
        res = await db[coll].delete_many({"tenant_id": {"$in": list(delete_tenant_ids)}})
        if res.deleted_count:
            print(f"  · {coll}: deleted {res.deleted_count} (tenant scope)")

    # Step 4 — delete the tenant docs themselves
    res = await db.tenants.delete_many({"id": {"$in": list(delete_tenant_ids)}})
    print(f"  · tenants: deleted {res.deleted_count}")

    # === KEPT TENANT — admin@consenso-agents.com — clean up ===
    admin = await db.users.find_one(
        {"email": "admin@consenso-agents.com"}, {"_id": 0}
    )
    if not admin:
        print("⚠ admin@consenso-agents.com not found, skipping deep cleanup.")
        return
    tid = admin["tenant_id"]
    print(f"\n=== Deep cleanup of tenant {tid[:8]}… (admin) ===")

    # Rename tenant
    await db.tenants.update_one({"id": tid}, {"$set": {"name": NEW_TENANT_NAME}})
    print(f"  · tenant renamed → '{NEW_TENANT_NAME}'")

    # Remove non-Abby agents (legacy "Aria" or any other)
    keep_pat = "|".join(KEEP_AGENT_NAME_SUBSTRINGS)
    res = await db.agents.delete_many({
        "tenant_id": tid,
        "name": {"$not": {"$regex": keep_pat, "$options": "i"}},
    })
    print(f"  · removed {res.deleted_count} non-Abby agent(s)")

    # Wipe ALL fixture conversations/messages/leads from this tenant
    for coll, scope_field in [
        ("conversations", "tenant_id"),
        ("messages", "tenant_id"),
        ("leads", "tenant_id"),
        ("tickets", "tenant_id"),
        ("audit_logs", "tenant_id"),
        ("metrics", "tenant_id"),
        ("events", "tenant_id"),
        ("qualifications", "tenant_id"),
    ]:
        if coll not in await db.list_collection_names():
            continue
        res = await db[coll].delete_many({scope_field: tid})
        if res.deleted_count:
            print(f"  · {coll}: deleted {res.deleted_count} fixture rows")

    # Remove orphan data sources (those NOT referenced by any kept agent)
    kept_agents = await db.agents.find({"tenant_id": tid}, {"_id": 0}).to_list(50)
    referenced = set()
    for a in kept_agents:
        for sid in (a.get("data_source_ids") or []):
            referenced.add(sid)
    res = await db.data_sources.delete_many({
        "tenant_id": tid,
        "id": {"$nin": list(referenced)},
    })
    if res.deleted_count:
        print(f"  · data_sources: removed {res.deleted_count} orphan source(s)")
    res = await db.data_chunks.delete_many({
        "tenant_id": tid,
        "source_id": {"$nin": list(referenced)},
    })
    if res.deleted_count:
        print(f"  · data_chunks: removed {res.deleted_count} orphan chunk(s)")

    # Final state report
    print("\n=== FINAL STATE ===")
    async for t in db.tenants.find({}, {"_id": 0}):
        u = await db.users.count_documents({"tenant_id": t["id"]})
        a = await db.agents.count_documents({"tenant_id": t["id"]})
        c = await db.conversations.count_documents({"tenant_id": t["id"]})
        l_count = await db.leads.count_documents({"tenant_id": t["id"]})
        print(f"  · {t['name']:24} | users={u} agents={a} convos={c} leads={l_count}")


if __name__ == "__main__":
    asyncio.run(run())
