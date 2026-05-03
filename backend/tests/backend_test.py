"""Backend API tests for Consenso Plus — multi-tenant AI BOS SaaS."""
import os
import uuid
import time
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
if not BASE_URL:
    # Read from frontend .env
    fe_env = Path(__file__).parent.parent.parent / "frontend" / ".env"
    for line in fe_env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@consenso.plus"
DEMO_PASSWORD = "demo1234"


# -------------------- Fixtures --------------------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def auth(session):
    r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text}"
    data = r.json()
    return {
        "token": data["token"],
        "user": data["user"],
        "tenant": data["tenant"],
        "headers": {"Authorization": f"Bearer {data['token']}", "Content-Type": "application/json"},
    }


# -------------------- Health --------------------
class TestHealth:
    def test_root(self, session):
        r = session.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# -------------------- Auth --------------------
class TestAuth:
    def test_login_demo(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == DEMO_EMAIL
        assert d["tenant"]["name"] == "Acme Corp"
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_login_invalid(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_me(self, session, auth):
        r = session.get(f"{API}/auth/me", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == DEMO_EMAIL
        assert d["tenant"]["id"] == auth["tenant"]["id"]

    def test_me_without_token(self, session):
        r = session.get(f"{API}/auth/me", timeout=10)
        assert r.status_code in (401, 403)

    def test_register_new_tenant(self, session):
        email = f"TEST_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(f"{API}/auth/register", json={
            "email": email, "password": "pass1234",
            "name": "Test Owner", "company_name": "TEST_Tenant_B",
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["user"]["email"] == email
        assert d["tenant"]["name"] == "TEST_Tenant_B"
        # Verify default agent and webchat integration created
        headers = {"Authorization": f"Bearer {d['token']}", "Content-Type": "application/json"}
        agents = session.get(f"{API}/agents", headers=headers, timeout=10).json()
        assert len(agents) >= 1
        integrations = session.get(f"{API}/integrations", headers=headers, timeout=10).json()
        assert any(i["kind"] == "webchat" for i in integrations)
        return {"headers": headers, "tenant_id": d["tenant"]["id"], "user_id": d["user"]["id"]}

    def test_register_duplicate(self, session):
        r = session.post(f"{API}/auth/register", json={
            "email": DEMO_EMAIL, "password": "x", "name": "X", "company_name": "Y",
        }, timeout=10)
        assert r.status_code == 409


# -------------------- Dashboard --------------------
class TestDashboard:
    def test_stats(self, session, auth):
        r = session.get(f"{API}/dashboard/stats", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("conversations", "leads", "open_tickets", "messages", "by_channel", "by_stage"):
            assert k in d
        assert d["conversations"] >= 3


# -------------------- Conversations --------------------
class TestConversations:
    def test_list(self, session, auth):
        r = session.get(f"{API}/conversations", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        convos = r.json()
        assert isinstance(convos, list) and len(convos) >= 3

    def test_get_conversation_with_messages(self, session, auth):
        convos = session.get(f"{API}/conversations", headers=auth["headers"], timeout=10).json()
        conv_id = convos[0]["id"]
        r = session.get(f"{API}/conversations/{conv_id}", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["conversation"]["id"] == conv_id
        assert isinstance(d["messages"], list) and len(d["messages"]) >= 1

    def test_takeover_release(self, session, auth):
        convos = session.get(f"{API}/conversations", headers=auth["headers"], timeout=10).json()
        # Pick one that is 'ai' to test takeover then release
        target = next((c for c in convos if c["status"] == "ai"), convos[0])
        conv_id = target["id"]
        r1 = session.post(f"{API}/conversations/{conv_id}/takeover", headers=auth["headers"], timeout=10)
        assert r1.status_code == 200
        assert r1.json()["status"] == "human"
        # Verify via GET
        got = session.get(f"{API}/conversations/{conv_id}", headers=auth["headers"], timeout=10).json()
        assert got["conversation"]["status"] == "human"
        r2 = session.post(f"{API}/conversations/{conv_id}/release", headers=auth["headers"], timeout=10)
        assert r2.status_code == 200
        got2 = session.get(f"{API}/conversations/{conv_id}", headers=auth["headers"], timeout=10).json()
        assert got2["conversation"]["status"] == "ai"

    def test_send_human_message(self, session, auth):
        convos = session.get(f"{API}/conversations", headers=auth["headers"], timeout=10).json()
        conv_id = convos[0]["id"]
        r = session.post(f"{API}/conversations/{conv_id}/messages", headers=auth["headers"],
                         json={"text": "TEST_agent reply from pytest"}, timeout=10)
        assert r.status_code == 200
        msg = r.json()
        assert msg["sender"] == "human"
        assert msg["text"] == "TEST_agent reply from pytest"
        # verify persisted via GET
        got = session.get(f"{API}/conversations/{conv_id}", headers=auth["headers"], timeout=10).json()
        assert any(m["id"] == msg["id"] for m in got["messages"])


# -------------------- Agents --------------------
class TestAgents:
    def test_list_agents(self, session, auth):
        r = session.get(f"{API}/agents", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_agent_crud(self, session, auth):
        payload = {
            "name": "TEST_Agent", "tone": "friendly", "goal": "help test",
            "system_prompt": "You are a test.", "rules": "",
            "model_provider": "auto", "model_name": "gpt-5.1",
            "tools": [{"key": "create_lead", "enabled": True}],
            "knowledge": "", "active": True,
        }
        r = session.post(f"{API}/agents", headers=auth["headers"], json=payload, timeout=10)
        assert r.status_code == 200, r.text
        agent = r.json()
        aid = agent["id"]
        assert agent["name"] == "TEST_Agent"

        # Update
        payload["name"] = "TEST_Agent_Updated"
        u = session.put(f"{API}/agents/{aid}", headers=auth["headers"], json=payload, timeout=10)
        assert u.status_code == 200
        assert u.json()["name"] == "TEST_Agent_Updated"

        # Verify in list
        lst = session.get(f"{API}/agents", headers=auth["headers"], timeout=10).json()
        assert any(a["id"] == aid and a["name"] == "TEST_Agent_Updated" for a in lst)

        # Delete
        d = session.delete(f"{API}/agents/{aid}", headers=auth["headers"], timeout=10)
        assert d.status_code == 200

    @pytest.mark.slow
    def test_agent_pipeline(self, session, auth):
        agents = session.get(f"{API}/agents", headers=auth["headers"], timeout=10).json()
        aid = agents[0]["id"]
        r = session.post(f"{API}/agents/{aid}/test", headers=auth["headers"],
                         json={"text": "What is the pricing for 50 seats?"}, timeout=90)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("intent", "structure", "decision", "reply"):
            assert k in d
        assert isinstance(d["reply"], str) and len(d["reply"]) > 0


# -------------------- Leads --------------------
class TestLeads:
    def test_lead_crud(self, session, auth):
        payload = {"name": "TEST_Lead", "email": "test_lead@x.io", "phone": None,
                   "company": "TestCo", "source": "manual", "stage": "new",
                   "score": 10, "notes": "test", "conversation_id": None}
        r = session.post(f"{API}/leads", headers=auth["headers"], json=payload, timeout=10)
        assert r.status_code == 200
        lead = r.json()
        lid = lead["id"]
        assert lead["name"] == "TEST_Lead"

        # update stage
        payload["stage"] = "qualified"
        u = session.put(f"{API}/leads/{lid}", headers=auth["headers"], json=payload, timeout=10)
        assert u.status_code == 200
        assert u.json()["stage"] == "qualified"

        # verify in list
        lst = session.get(f"{API}/leads", headers=auth["headers"], timeout=10).json()
        assert any(lead_item["id"] == lid for lead_item in lst)

        # delete
        session.delete(f"{API}/leads/{lid}", headers=auth["headers"], timeout=10)


# -------------------- Tickets --------------------
class TestTickets:
    def test_ticket_crud(self, session, auth):
        payload = {"subject": "TEST_Ticket", "description": "t desc", "priority": "medium",
                   "status": "open", "assigned_to": None, "conversation_id": None}
        r = session.post(f"{API}/tickets", headers=auth["headers"], json=payload, timeout=10)
        assert r.status_code == 200
        tid = r.json()["id"]
        payload["status"] = "in_progress"
        u = session.put(f"{API}/tickets/{tid}", headers=auth["headers"], json=payload, timeout=10)
        assert u.status_code == 200
        assert u.json()["status"] == "in_progress"
        session.delete(f"{API}/tickets/{tid}", headers=auth["headers"], timeout=10)


# -------------------- Integrations --------------------
class TestIntegrations:
    def test_list(self, session, auth):
        r = session.get(f"{API}/integrations", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        items = r.json()
        # 5 channels + 4 crm = 9
        assert len(items) >= 9
        channels = [i for i in items if i["category"] == "channel"]
        crm = [i for i in items if i["category"] == "crm"]
        assert len(channels) >= 5
        assert len(crm) >= 4

    def test_update_status(self, session, auth):
        items = session.get(f"{API}/integrations", headers=auth["headers"], timeout=10).json()
        # Pick a disconnected one
        target = next(i for i in items if i["status"] == "disconnected")
        r = session.put(f"{API}/integrations/{target['id']}", headers=auth["headers"],
                        json={"status": "connected"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "connected"
        # Revert
        session.put(f"{API}/integrations/{target['id']}", headers=auth["headers"],
                    json={"status": "disconnected"}, timeout=10)


# -------------------- Team --------------------
class TestTeam:
    def test_team_invite_remove(self, session, auth):
        email = f"TEST_member_{uuid.uuid4().hex[:6]}@x.io"
        r = session.post(f"{API}/team/invite", headers=auth["headers"],
                         json={"email": email, "name": "TEST_Member", "password": "pw123456", "role": "agent"}, timeout=10)
        assert r.status_code == 200
        uid = r.json()["id"]
        lst = session.get(f"{API}/team", headers=auth["headers"], timeout=10).json()
        assert any(u["id"] == uid for u in lst)
        # Remove
        d = session.delete(f"{API}/team/{uid}", headers=auth["headers"], timeout=10)
        assert d.status_code == 200
        lst2 = session.get(f"{API}/team", headers=auth["headers"], timeout=10).json()
        assert not any(u["id"] == uid for u in lst2)


# -------------------- Admin --------------------
class TestAdmin:
    def test_admin_tenants(self, session, auth):
        r = session.get(f"{API}/admin/tenants", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# -------------------- Tenant Isolation --------------------
class TestTenantIsolation:
    def test_isolation_new_tenant_sees_no_demo_data(self, session):
        # Register new tenant
        email = f"TEST_iso_{uuid.uuid4().hex[:6]}@x.io"
        r = session.post(f"{API}/auth/register", json={
            "email": email, "password": "pw123456",
            "name": "Iso Owner", "company_name": "TEST_IsoTenant",
        }, timeout=15)
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['token']}", "Content-Type": "application/json"}
        # Conversations should be empty (demo tenant has 3)
        convos = session.get(f"{API}/conversations", headers=h, timeout=10).json()
        assert convos == [] or len(convos) == 0
        # Leads should be empty
        leads = session.get(f"{API}/leads", headers=h, timeout=10).json()
        assert leads == [] or len(leads) == 0


# -------------------- Inbound Simulate (AI pipeline) --------------------
class TestInboundPipeline:
    @pytest.mark.slow
    def test_inbound_simulate(self, session, auth):
        payload = {
            "channel": "webchat",
            "external_user_id": f"TEST_user_{uuid.uuid4().hex[:6]}",
            "contact_name": "TEST Inbound User",
            "text": "Hi, I want to buy your product. What are the prices for 100 users?",
        }
        # Retry once on timeout/5xx
        last = None
        for attempt in range(2):
            try:
                r = session.post(f"{API}/inbound/simulate", headers=auth["headers"], json=payload, timeout=90)
                last = r
                if r.status_code == 200:
                    break
            except requests.Timeout:
                time.sleep(2)
        assert last is not None and last.status_code == 200, f"inbound pipeline failed: {last.status_code if last else 'timeout'} {last.text if last else ''}"
        d = last.json()
        assert "conversation_id" in d
        assert "auto_reply" in d and isinstance(d["auto_reply"], str) and len(d["auto_reply"]) > 0
        assert "intent" in d and "structure" in d
        # Validate the conversation now exists
        convo = session.get(f"{API}/conversations/{d['conversation_id']}", headers=auth["headers"], timeout=10).json()
        msgs = convo["messages"]
        # Must have at least our user msg and AI reply
        assert any(m["sender"] == "user" for m in msgs)
        assert any(m["sender"] == "ai" for m in msgs)
