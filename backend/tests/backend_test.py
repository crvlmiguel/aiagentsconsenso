"""Backend API tests for Consenso Plus v2.0 — PT-PT pivot with data sources, cards, WS, widget.

NOTA (v3.4): Este ficheiro foi escrito contra a arquitetura v2.0 (canais geridos a
nível de tenant, seed "Imobiliária Lisboa"). Após a migração agent-centric (v3.0+) e
a re-criação dos tenants, vários assertions já não correspondem (nome de tenant,
estrutura de seeds). Mantido como referência histórica — substituído por
test_crm_qualify.py + test_widget.py + test_webhooks_iter7.py.
"""
import pytest

pytestmark = pytest.mark.skip(reason="Legacy v2 suite — substituída pelos testes v3 (test_crm_qualify, test_widget, test_webhooks_iter7).")

import os
import json
import uuid
import time
import asyncio
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
        d = r.json()
        assert d["status"] == "ok"
        assert d["name"] == "Consenso Plus"
        assert d["version"].startswith("2.")


# -------------------- Auth --------------------
class TestAuth:
    def test_login_demo(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["user"]["email"] == DEMO_EMAIL
        # v2 seed is Imobiliária Lisboa
        assert "Imob" in d["tenant"]["name"] or "lisboa" in d["tenant"]["name"].lower()
        assert isinstance(d["token"], str) and len(d["token"]) > 20

    def test_login_invalid(self, session):
        r = session.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_me(self, session, auth):
        r = session.get(f"{API}/auth/me", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        assert r.json()["user"]["email"] == DEMO_EMAIL

    def test_register_new_tenant(self, session):
        email = f"TEST_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(f"{API}/auth/register", json={
            "email": email, "password": "pass1234",
            "name": "Test Owner", "company_name": "TEST_Tenant_V2",
        }, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["tenant"]["name"] == "TEST_Tenant_V2"


# -------------------- Dashboard --------------------
class TestDashboard:
    def test_stats(self, session, auth):
        r = session.get(f"{API}/dashboard/stats", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        d = r.json()
        for k in ("conversations", "leads", "open_tickets", "messages", "by_channel", "by_stage"):
            assert k in d


# -------------------- Data Sources (NEW v2) --------------------
class TestDataSources:
    def test_list_sources_has_seed(self, session, auth):
        r = session.get(f"{API}/data-sources", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        sources = r.json()
        assert isinstance(sources, list) and len(sources) >= 1
        # Check seeded catalogue exists with chunks and items
        seeded = next((s for s in sources if "imóveis" in s["name"].lower() or "imoveis" in s["name"].lower() or "catál" in s["name"].lower()), None)
        assert seeded is not None, f"Seeded real-estate source not found. Got: {[s['name'] for s in sources]}"
        assert seeded["chunks"] > 0, "Seeded source has 0 chunks"
        assert seeded["items"] > 0, "Seeded source has 0 items"
        assert seeded["status"] == "indexed"

    def test_create_text_source(self, session, auth):
        payload = {"name": "TEST_TextSource", "text": "Consenso Plus é uma plataforma AI para negócios. Suporta múltiplos canais."}
        r = session.post(f"{API}/data-sources/text", headers=auth["headers"], json=payload, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == "TEST_TextSource"
        assert d["kind"] == "text"
        assert d["status"] == "indexed"
        assert d["chunks"] > 0
        # Verify it appears in list
        lst = session.get(f"{API}/data-sources", headers=auth["headers"], timeout=10).json()
        assert any(s["id"] == d["id"] for s in lst)
        # cleanup
        session.delete(f"{API}/data-sources/{d['id']}", headers=auth["headers"], timeout=10)

    def test_create_url_source(self, session, auth):
        payload = {"name": "TEST_URL", "url": "https://example.com"}
        r = session.post(f"{API}/data-sources/url", headers=auth["headers"], json=payload, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["kind"] == "url"
        assert d["status"] in ("indexed", "error")  # may fail if sandbox has no egress
        # cleanup
        session.delete(f"{API}/data-sources/{d['id']}", headers=auth["headers"], timeout=10)

    def test_delete_source_removes_chunks(self, session, auth):
        # create
        c = session.post(f"{API}/data-sources/text", headers=auth["headers"],
                         json={"name": "TEST_ToDelete", "text": "Delete me please. " * 50}, timeout=10).json()
        sid = c["id"]
        # delete
        d = session.delete(f"{API}/data-sources/{sid}", headers=auth["headers"], timeout=10)
        assert d.status_code == 200
        # verify gone
        lst = session.get(f"{API}/data-sources", headers=auth["headers"], timeout=10).json()
        assert not any(s["id"] == sid for s in lst)


# -------------------- Agents & AI Pipeline (cards validation) --------------------
class TestAgentPipeline:
    def test_list_agents(self, session, auth):
        r = session.get(f"{API}/agents", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) >= 1
        # Seed agent is "Aria"
        assert any("aria" in a["name"].lower() for a in agents)

    @pytest.mark.slow
    def test_agent_pipeline_returns_cards_pt(self, session, auth):
        agents = session.get(f"{API}/agents", headers=auth["headers"], timeout=10).json()
        aid = agents[0]["id"]
        r = session.post(f"{API}/agents/{aid}/test", headers=auth["headers"],
                         json={"text": "Quero ver imóveis T3 em Lisboa"}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("intent", "structure", "decision", "reply", "cards", "language", "retrieved"):
            assert k in d, f"missing key {k} in response keys={list(d.keys())}"
        assert isinstance(d["reply"], str) and len(d["reply"]) > 0
        assert isinstance(d["cards"], list)
        assert isinstance(d["retrieved"], list)
        # Portuguese query should be detected
        assert d["language"] in ("pt", "pt-pt"), f"expected pt got {d['language']}"
        # retrieved should have items from seeded catalogue
        assert len(d["retrieved"]) > 0, "retrieval returned empty — seed may not be indexed"
        # Cards should be populated when retrieval has items
        has_item = any(r.get("kind") == "item" for r in d["retrieved"])
        if has_item:
            assert len(d["cards"]) > 0, f"cards empty despite retrieved items. reply={d['reply'][:200]}"
            card = d["cards"][0]
            assert "title" in card

    @pytest.mark.slow
    def test_language_detection_english(self, session, auth):
        agents = session.get(f"{API}/agents", headers=auth["headers"], timeout=10).json()
        aid = agents[0]["id"]
        r = session.post(f"{API}/agents/{aid}/test", headers=auth["headers"],
                         json={"text": "Hello, I am looking for a 3 bedroom apartment in downtown with a big kitchen and garage included please."},
                         timeout=120)
        assert r.status_code == 200
        d = r.json()
        assert d["language"] == "en", f"expected en got {d['language']}"


# -------------------- Inbound simulate --------------------
class TestInbound:
    @pytest.mark.slow
    def test_inbound_sales_creates_lead_with_tags(self, session, auth):
        payload = {
            "channel": "webchat",
            "external_user_id": f"TEST_user_{uuid.uuid4().hex[:6]}",
            "contact_name": "TEST Compra Lisboa",
            "text": "Olá, quero comprar um T3 em Lisboa com varanda. Qual o preço?",
        }
        r = session.post(f"{API}/inbound/simulate", headers=auth["headers"], json=payload, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "conversation_id" in d
        assert isinstance(d.get("reply"), str) and len(d["reply"]) > 0
        assert "cards" in d
        assert "intent" in d and "structure" in d


# -------------------- Webchat public endpoint --------------------
class TestWebchat:
    def test_webchat_no_auth(self, session, auth):
        tenant_id = auth["tenant"]["id"]
        payload = {
            "channel": "webchat",
            "external_user_id": f"TEST_w_{uuid.uuid4().hex[:6]}",
            "contact_name": "TEST Widget User",
            "text": "Olá",
        }
        # Public - no auth header
        s = requests.Session()
        s.headers.update({"Content-Type": "application/json"})
        r = s.post(f"{API}/webchat/{tenant_id}/message", json=payload, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "conversation_id" in d
        assert "reply" in d

    def test_webchat_bad_tenant(self, session):
        s = requests.Session()
        r = s.post(f"{API}/webchat/nonexistent-tenant-id/message",
                   json={"channel": "webchat", "external_user_id": "x", "contact_name": "x", "text": "hi"},
                   timeout=10)
        assert r.status_code == 404


# -------------------- Widget HTML --------------------
class TestWidget:
    def test_widget_html(self, session, auth):
        tenant_id = auth["tenant"]["id"]
        # Note: non-/api /widget path is routed to frontend by ingress.
        # Backend also exposes /api/widget/{tenant_id} which is the reliable path.
        r = requests.get(f"{API}/widget/{tenant_id}", timeout=10)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")
        assert "Assistente" in r.text
        assert "0069FE" in r.text  # primary color
        assert "/webchat/" in r.text


# -------------------- WebSocket --------------------
class TestWebSocket:
    def test_ws_connect(self, auth):
        try:
            import websocket  # websocket-client
        except ImportError:
            pytest.skip("websocket-client not installed")
        tenant_id = auth["tenant"]["id"]
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + f"/api/ws/{tenant_id}"
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            assert ws.connected
            ws.close()
        except Exception as e:
            pytest.fail(f"WS connection failed: {e}")


# -------------------- Conversations (seed) --------------------
class TestConversations:
    def test_list_has_seed(self, session, auth):
        r = session.get(f"{API}/conversations", headers=auth["headers"], timeout=10)
        assert r.status_code == 200
        convos = r.json()
        assert isinstance(convos, list) and len(convos) >= 3
        # seed contacts: Ana, João, Rita
        names = " ".join(c.get("contact_name", "") for c in convos)
        assert "Ana" in names
