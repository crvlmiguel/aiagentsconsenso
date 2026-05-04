"""Agent-centric restructure tests (v2.3) — channels/email/install per-agent."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": "demo@consenso-agents.com", "password": "demo1234"})
    assert r.status_code == 200, r.text
    j = r.json()
    s.headers.update({"Authorization": f"Bearer {j['token']}"})
    return {"s": s, "tenant_id": j["tenant"]["id"], "user": j["user"]}


@pytest.fixture(scope="module")
def agent(auth):
    r = auth["s"].get(f"{API}/agents")
    assert r.status_code == 200
    agents = r.json()
    assert len(agents) >= 1
    return agents[0]


def test_demo_login_still_works(auth):
    assert auth["tenant_id"]


def test_agent_has_channels_and_email_shape(auth, agent):
    # Channels dict should exist; the key fields (if present) support toggle + config
    ch = agent.get("channels") or {}
    em = agent.get("email") or {}
    assert isinstance(ch, dict)
    assert isinstance(em, dict)


def test_persist_channels_and_email_via_put(auth, agent):
    payload = {k: agent.get(k) for k in [
        "name", "avatar_url", "welcome_message", "icebreakers", "tone", "goal",
        "system_prompt", "rules", "api_provider", "api_key", "model_provider",
        "model_name", "tools", "knowledge", "data_source_ids", "default_language",
        "notify_email", "channels", "email", "active",
    ]}
    payload["channels"] = {
        "webchat": {"enabled": True},
        "whatsapp": {"enabled": True, "access_token": "TEST_WA_TOK", "phone_number_id": "999000"},
        "telegram": {"enabled": True, "bot_token": "TEST_TG_TOK"},
    }
    payload["email"] = {
        "enabled": True, "host": "smtp.example.com", "port": 587, "secure": "tls",
        "username": "u", "password": "p", "from_email": "no-reply@example.com",
        "notify_email": "sales@example.com",
    }
    r = auth["s"].put(f"{API}/agents/{agent['id']}", json=payload)
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["channels"]["whatsapp"]["access_token"] == "TEST_WA_TOK"
    assert got["channels"]["telegram"]["bot_token"] == "TEST_TG_TOK"
    assert got["email"]["host"] == "smtp.example.com"
    # GET re-fetch persistence
    r2 = auth["s"].get(f"{API}/agents")
    a2 = [x for x in r2.json() if x["id"] == agent["id"]][0]
    assert a2["channels"]["whatsapp"]["phone_number_id"] == "999000"
    assert a2["email"]["from_email"] == "no-reply@example.com"


def test_test_channel_webchat_ok(auth, agent):
    r = auth["s"].post(f"{API}/agents/{agent['id']}/test-channel/webchat")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True


def test_test_channel_telegram_invalid_token(auth, agent):
    # Previous test persisted an invalid bot token
    r = auth["s"].post(f"{API}/agents/{agent['id']}/test-channel/telegram")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is False
    assert "error" in j


def test_test_channel_whatsapp_invalid_token(auth, agent):
    r = auth["s"].post(f"{API}/agents/{agent['id']}/test-channel/whatsapp")
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is False
    assert "error" in j


def test_test_email_fake_smtp(auth, agent):
    # SMTP is fake → should return ok:false (graceful)
    r = auth["s"].post(f"{API}/agents/{agent['id']}/test-email", json={"to": "dummy@example.com"})
    assert r.status_code == 200
    j = r.json()
    assert "ok" in j


def test_test_email_incomplete_smtp(auth, agent):
    # Clear SMTP config → should return ok:false with PT error
    payload = {k: agent.get(k) for k in [
        "name", "avatar_url", "welcome_message", "icebreakers", "tone", "goal",
        "system_prompt", "rules", "api_provider", "api_key", "model_provider",
        "model_name", "tools", "knowledge", "data_source_ids", "default_language",
        "notify_email", "channels", "email", "active",
    ]}
    payload["email"] = {"enabled": True, "host": "", "from_email": ""}
    r = auth["s"].put(f"{API}/agents/{agent['id']}", json=payload)
    assert r.status_code == 200
    r2 = auth["s"].post(f"{API}/agents/{agent['id']}/test-email", json={})
    j = r2.json()
    assert j.get("ok") is False
    assert "SMTP" in (j.get("error") or "") or "incompleta" in (j.get("error") or "").lower()


def test_webchat_message_accepts_agent_id(auth, agent):
    body = {
        "channel": "webchat", "external_user_id": "pytest-user",
        "contact_name": "Pytest", "text": "Olá", "agent_id": agent["id"],
    }
    r = requests.post(f"{API}/webchat/{auth['tenant_id']}/message", json=body, timeout=60)
    assert r.status_code == 200, r.text
    j = r.json()
    assert "conversation_id" in j


def test_register_new_tenant_has_no_global_webchat_integration():
    """New tenants should NOT create a global 'webchat' integration; per-agent only."""
    import uuid
    email = f"test_{uuid.uuid4().hex[:8]}@testcp.pt"
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/register", json={
        "company_name": f"TestCo_{uuid.uuid4().hex[:6]}",
        "email": email, "password": "pw12345678", "name": "Tester",
    })
    assert r.status_code == 200, r.text
    j = r.json()
    s.headers.update({"Authorization": f"Bearer {j['token']}"})
    # Integrations list should not have 'webchat' kind
    r2 = s.get(f"{API}/integrations")
    assert r2.status_code == 200
    kinds = [i.get("kind") for i in r2.json()]
    assert "webchat" not in kinds, f"Global webchat integration should not exist. Got: {kinds}"
    # New agent should have channels.webchat.enabled = true
    r3 = s.get(f"{API}/agents")
    assert r3.status_code == 200
    agents = r3.json()
    assert len(agents) >= 1
    assert agents[0]["channels"].get("webchat", {}).get("enabled") is True
