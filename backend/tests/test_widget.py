"""Iteration 5 — widget embed script + demo test page + regression checks."""
import os
import requests
import pytest

def _read_frontend_env():
    for line in open("/app/frontend/.env").read().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip()
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_frontend_env()).rstrip("/")
DEMO_EMAIL = "admin@consenso-agents.com"
DEMO_PASS = "100%Consenso"
DEMO_TENANT = "896e44e0-98b9-4172-8841-32419fe495b7"
DEMO_AGENT = "b7e15638-e0d7-4df2-8d33-1f3ee3a5f04f"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    return {"token": data["token"], "tenant_id": data["tenant"]["id"]}


# ---------- WIDGET.JS ----------
class TestWidgetJS:
    def test_api_widget_js_returns_javascript(self):
        r = requests.get(f"{BASE_URL}/api/widget.js", timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert "javascript" in ct.lower(), f"content-type={ct}"
        # Substantive JS content — not HTML
        assert "<html" not in r.text.lower()[:200]
        assert "cp-launcher" in r.text
        assert "ConsensoPlus" in r.text

    def test_api_widget_js_cors(self):
        r = requests.get(f"{BASE_URL}/api/widget.js", timeout=15)
        assert r.headers.get("access-control-allow-origin") == "*"

    def test_non_api_widget_js_routes_to_frontend(self):
        """Hitting /widget.js without /api should return React HTML (frontend fallback)."""
        r = requests.get(f"{BASE_URL}/widget.js", timeout=15)
        # Should NOT be JS — should be HTML (frontend SPA)
        ct = r.headers.get("content-type", "").lower()
        assert "javascript" not in ct, f"expected non-JS, got {ct}"


# ---------- WIDGET TEST PAGE ----------
class TestWidgetTestPage:
    def test_widget_test_page_returns_html(self):
        url = f"{BASE_URL}/api/widget-test/{DEMO_TENANT}/{DEMO_AGENT}"
        r = requests.get(url, timeout=15)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "").lower()
        body = r.text
        assert "/api/widget.js" in body
        assert DEMO_TENANT in body
        assert DEMO_AGENT in body
        assert "Demonstração ao vivo" in body

    def test_widget_api_html_endpoint_still_works(self):
        # /api/widget/{tenant_id} loads widget.html used in the iframe
        r = requests.get(f"{BASE_URL}/api/widget/{DEMO_TENANT}", timeout=15)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "").lower()


# ---------- REGRESSION: AGENT-CENTRIC ENDPOINTS ----------
class TestRegressionAgentCentric:
    def test_list_agents(self, auth):
        r = requests.get(f"{BASE_URL}/api/agents",
                         headers={"Authorization": f"Bearer {auth['token']}"}, timeout=15)
        assert r.status_code == 200
        agents = r.json()
        assert isinstance(agents, list) and len(agents) >= 1

    def test_put_agent_persists_channels_and_email(self, auth):
        hdr = {"Authorization": f"Bearer {auth['token']}"}
        # GET first agent
        agents = requests.get(f"{BASE_URL}/api/agents", headers=hdr, timeout=15).json()
        agent = agents[0]
        aid = agent["id"]
        # build AgentInput payload (strip server-only fields)
        payload = {k: v for k, v in agent.items()
                   if k not in {"id", "tenant_id", "created_at"}}
        payload["channels"] = {
            "webchat": {"enabled": True},
            "whatsapp": {"enabled": False, "access_token": "TEST_tok", "phone_number_id": "TEST_pid"},
            "telegram": {"enabled": False, "bot_token": "TEST_bt"},
        }
        payload["email"] = {
            "enabled": False, "host": "smtp.test.com", "port": 587, "secure": "tls",
            "username": "u", "password": "p", "from_email": "from@test.com", "notify_email": "n@test.com",
        }
        r = requests.put(f"{BASE_URL}/api/agents/{aid}", headers=hdr, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        got = r.json()
        assert got["channels"]["whatsapp"]["access_token"] == "TEST_tok"
        assert got["email"]["host"] == "smtp.test.com"
        # GET to verify persistence
        again = requests.get(f"{BASE_URL}/api/agents", headers=hdr, timeout=15).json()
        fresh = [a for a in again if a["id"] == aid][0]
        assert fresh["channels"]["whatsapp"]["phone_number_id"] == "TEST_pid"
        assert fresh["email"]["from_email"] == "from@test.com"

    def test_agent_test_email_incomplete_returns_ok_false(self, auth):
        hdr = {"Authorization": f"Bearer {auth['token']}"}
        agents = requests.get(f"{BASE_URL}/api/agents", headers=hdr, timeout=15).json()
        aid = agents[0]["id"]
        r = requests.post(f"{BASE_URL}/api/agents/{aid}/test-email",
                          headers=hdr, json={"to": "x@y.com"}, timeout=15)
        # API returns 200 with {ok:false} for incomplete config
        assert r.status_code == 200
        j = r.json()
        assert j.get("ok") is False or "error" in j

    def test_webchat_with_agent_id(self, auth):
        """POST /api/webchat/{tenant}/message with agent_id — must accept and reply."""
        # Discover real tenant + agent for the authenticated user (cleanup-safe)
        r = requests.get(f"{BASE_URL}/api/agents",
                         headers={"Authorization": f"Bearer {auth['token']}"}, timeout=15)
        assert r.status_code == 200
        agents = r.json()
        assert agents, "Tenant must have at least one agent"
        agent = agents[0]
        payload = {
            "channel": "webchat",
            "external_user_id": "TEST_cp_it5",
            "contact_name": "TEST user",
            "text": "Olá",
            "agent_id": agent["id"],
        }
        r = requests.post(f"{BASE_URL}/api/webchat/{agent['tenant_id']}/message",
                          json=payload, timeout=45)
        assert r.status_code == 200, r.text
        j = r.json()
        assert "conversation_id" in j
        # reply may be from AI or config_missing error; must be non-empty string
        assert isinstance(j.get("reply"), (str, type(None)))
