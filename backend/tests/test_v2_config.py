"""Backend tests for v2.x: per-agent API config, channel config validation, SMTP test, AI pipeline PT errors, tenant isolation.

NOTA (v3.4): Suite v2 — espera "integrations" colection ao nível do tenant, mas
desde v3.0 os canais e SMTP vivem dentro de cada agente (agent-centric). Mantido
como referência; substituído pelos testes v3.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Legacy v2 suite — schema 'integrations' substituído por canais/email por agente em v3.0.")

import os
import uuid
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    fe_env = Path(__file__).parent.parent.parent / "frontend" / ".env"
    for line in fe_env.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

DEMO_EMAIL = "demo@consenso-agents.com"
DEMO_PASSWORD = "demo1234"


@pytest.fixture(scope="module")
def auth():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    return {
        "session": s,
        "token": d["token"],
        "tenant": d["tenant"],
        "headers": {"Authorization": f"Bearer {d['token']}", "Content-Type": "application/json"},
    }


# ---------- Inline /api/test-connection ----------
class TestInlineTestConnection:
    def test_emergent_no_key_ok(self, auth):
        r = requests.post(f"{API}/test-connection",
                          headers=auth["headers"],
                          json={"api_provider": "emergent"}, timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True, f"expected ok:true, got {d}"
        assert "provider" in d and "model" in d

    def test_openai_invalid_key_returns_ok_false(self, auth):
        r = requests.post(f"{API}/test-connection",
                          headers=auth["headers"],
                          json={"api_provider": "openai", "api_key": "sk-INVALID-12345", "model_name": "gpt-5.1"},
                          timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is False
        assert d.get("error"), "expected an error message"


# ---------- Per-agent /agents/{id}/test-connection ----------
class TestAgentTestConnection:
    def test_seeded_agent_ok(self, auth):
        agents = auth["session"].get(f"{API}/agents", headers=auth["headers"], timeout=10).json()
        aria = next((a for a in agents if "aria" in a["name"].lower()), agents[0])
        r = requests.post(f"{API}/agents/{aria['id']}/test-connection",
                          headers=auth["headers"], timeout=60)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True, f"Aria test failed: {d}"
        assert d.get("provider") and d.get("model")

    def test_agent_openai_empty_key_blocks_test(self, auth):
        # Create agent with provider openai and empty key
        body = {
            "name": f"TEST_NoKey_{uuid.uuid4().hex[:6]}",
            "tone": "neutro", "goal": "teste",
            "system_prompt": "teste",
            "api_provider": "openai", "api_key": "",
            "model_provider": "openai", "model_name": "gpt-5.1",
            "tools": [], "active": True,
        }
        c = requests.post(f"{API}/agents", headers=auth["headers"], json=body, timeout=15)
        assert c.status_code == 200, c.text
        aid = c.json()["id"]
        try:
            # /test should return 400 PT
            r = requests.post(f"{API}/agents/{aid}/test",
                              headers=auth["headers"],
                              json={"text": "olá"}, timeout=30)
            assert r.status_code == 400, f"expected 400, got {r.status_code} {r.text}"
            detail = r.json().get("detail", "")
            assert "configure a API da IA" in detail, f"expected PT message, got: {detail}"
        finally:
            requests.delete(f"{API}/agents/{aid}", headers=auth["headers"], timeout=10)


# ---------- Aria /agents/{id}/test pipeline (PT-PT, cards) ----------
class TestAriaPipeline:
    @pytest.mark.slow
    def test_aria_pt_query_returns_reply_and_cards(self, auth):
        agents = auth["session"].get(f"{API}/agents", headers=auth["headers"], timeout=10).json()
        aria = next((a for a in agents if "aria" in a["name"].lower()), agents[0])
        r = requests.post(f"{API}/agents/{aria['id']}/test",
                          headers=auth["headers"],
                          json={"text": "Quero T3 em Lisboa"}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert isinstance(d.get("reply"), str) and len(d["reply"]) > 0
        assert "cards" in d
        assert d.get("language") in ("pt", "pt-pt")
        assert "intent" in d and "structure" in d


# ---------- Inbound simulate ----------
class TestInboundSimulate:
    @pytest.mark.slow
    def test_inbound_pt_returns_structured(self, auth):
        payload = {
            "channel": "webchat",
            "external_user_id": f"TEST_u_{uuid.uuid4().hex[:6]}",
            "contact_name": "TEST PT",
            "text": "Quero T3 em Lisboa",
        }
        r = requests.post(f"{API}/inbound/simulate", headers=auth["headers"], json=payload, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("conversation_id", "reply", "cards", "intent", "structure"):
            assert k in d, f"missing {k} in {list(d.keys())}"


# ---------- Integration config validation ----------
class TestIntegrationConfig:
    def _get_int(self, auth, kind):
        items = auth["session"].get(f"{API}/integrations", headers=auth["headers"], timeout=10).json()
        return next((x for x in items if x["kind"] == kind), None)

    def test_whatsapp_missing_fields_blocks_connect(self, auth):
        wa = self._get_int(auth, "whatsapp")
        assert wa, "seed missing whatsapp integration"
        # Reset config explicitly (empty strings overwrite stale values from prior test runs)
        requests.put(f"{API}/integrations/{wa['id']}",
                     headers=auth["headers"],
                     json={"status": "disconnected",
                           "config": {"access_token": "", "phone_number_id": ""}}, timeout=10)
        r = requests.put(f"{API}/integrations/{wa['id']}",
                         headers=auth["headers"],
                         json={"status": "connected",
                               "config": {"access_token": "", "phone_number_id": ""}}, timeout=10)
        assert r.status_code == 400, f"got {r.status_code} {r.text}"
        detail = r.json().get("detail", "")
        assert "Configuração incompleta" in detail
        assert "access_token" in detail and "phone_number_id" in detail

    def test_instagram_missing_fields_blocks_connect(self, auth):
        ig = self._get_int(auth, "instagram")
        assert ig
        requests.put(f"{API}/integrations/{ig['id']}",
                     headers=auth["headers"],
                     json={"status": "disconnected",
                           "config": {"access_token": "", "page_id": ""}}, timeout=10)
        r = requests.put(f"{API}/integrations/{ig['id']}",
                         headers=auth["headers"],
                         json={"status": "connected", "config": {"access_token": "x"}}, timeout=10)
        assert r.status_code == 400
        assert "page_id" in r.json().get("detail", "")

    def test_telegram_missing_fields(self, auth):
        tg = self._get_int(auth, "telegram")
        assert tg
        requests.put(f"{API}/integrations/{tg['id']}",
                     headers=auth["headers"],
                     json={"status": "disconnected",
                           "config": {"bot_token": ""}}, timeout=10)
        r = requests.put(f"{API}/integrations/{tg['id']}",
                         headers=auth["headers"],
                         json={"status": "connected", "config": {}}, timeout=10)
        assert r.status_code == 400
        assert "bot_token" in r.json().get("detail", "")

    def test_smtp_missing_fields(self, auth):
        smtp = self._get_int(auth, "smtp")
        assert smtp
        # Reset config explicitly with empty strings
        requests.put(f"{API}/integrations/{smtp['id']}",
                     headers=auth["headers"],
                     json={"status": "disconnected",
                           "config": {"host": "", "port": "", "from_email": ""}}, timeout=10)
        r = requests.put(f"{API}/integrations/{smtp['id']}",
                         headers=auth["headers"],
                         json={"status": "connected", "config": {"host": "smtp.x.com"}}, timeout=10)
        assert r.status_code == 400, f"got {r.status_code} {r.text}"
        d = r.json().get("detail", "")
        assert "port" in d and "from_email" in d

    def test_whatsapp_valid_config_connects(self, auth):
        wa = self._get_int(auth, "whatsapp")
        r = requests.put(f"{API}/integrations/{wa['id']}",
                         headers=auth["headers"],
                         json={"status": "connected",
                               "config": {"access_token": "TEST_tok", "phone_number_id": "TEST_pid"}},
                         timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "connected"
        assert d["config"]["access_token"] == "TEST_tok"

        # GET to verify persistence
        items = auth["session"].get(f"{API}/integrations", headers=auth["headers"], timeout=10).json()
        again = next(x for x in items if x["id"] == wa["id"])
        assert again["status"] == "connected"
        assert again["config"]["phone_number_id"] == "TEST_pid"

    def test_smtp_test_email_no_500(self, auth):
        smtp = self._get_int(auth, "smtp")
        # Configure with fake creds
        requests.put(f"{API}/integrations/{smtp['id']}",
                     headers=auth["headers"],
                     json={"status": "connected",
                           "config": {"host": "smtp.invalid.local", "port": 587,
                                      "from_email": "noreply@example.com",
                                      "username": "u", "password": "p", "secure": "tls"}},
                     timeout=10)
        r = requests.post(f"{API}/integrations/{smtp['id']}/test-email",
                          headers=auth["headers"],
                          json={"to": "test@example.com"}, timeout=30)
        # Should NOT 500. Either 200 with ok:false, or 400 with detail.
        assert r.status_code in (200, 400), f"got {r.status_code} {r.text}"
        if r.status_code == 200:
            d = r.json()
            # smtp will fail to connect to invalid host gracefully
            assert "ok" in d


# ---------- Tenant isolation ----------
class TestTenantIsolation:
    def test_other_tenant_cannot_see_demo_agents(self, auth):
        # Register a new tenant
        s = requests.Session()
        email = f"TEST_iso_{uuid.uuid4().hex[:8]}@example.com"
        r = s.post(f"{API}/auth/register", json={
            "email": email, "password": "pass1234",
            "name": "Iso Owner", "company_name": "TEST_Iso_Tenant",
        }, timeout=15)
        assert r.status_code == 200, r.text
        token = r.json()["token"]
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # The new tenant should have ITS OWN agent (created on register), not Aria
        agents = s.get(f"{API}/agents", headers=h, timeout=10).json()
        assert all("aria" not in a["name"].lower() for a in agents), "Aria leaked to TEST tenant"

        # Integrations should not include Aria's tenant ones
        ints = s.get(f"{API}/integrations", headers=h, timeout=10).json()
        for i in ints:
            assert i["tenant_id"] != auth["tenant"]["id"]
