"""Iteration 18 — Guardrails + anti-duplicate + scheduling link + URL whitelist.

Tests the bug-fix bundle:
- Anti-repetition of already-answered questions (memory.py + guardrails.scrub_repeated_questions)
- Anti-duplicate for identical user messages sent < 5s apart
- New Agent fields: scheduling_link + allowed_domains (PUT/GET)
- ensure_scheduling_link injects the pipedrive URL when user shows intent
- filter_urls_by_whitelist strips URLs outside allow-list
- reset-defaults cleans agent state at the end
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for direct pytest runs — but production expects env var
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASS = "100%Consenso"

PIPEDRIVE_LINK = "https://consensoglobal.pipedrive.com/scheduler/1DzB0QCb/agende-uma-reuniao"
ALLOWED = ["consenso-plus.com", "consensoglobal.pipedrive.com"]


# ============ Fixtures ============
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    data = r.json()
    s.headers.update({"Authorization": f"Bearer {data['token']}"})
    s.tenant_id = data["tenant"]["id"]
    return s


@pytest.fixture(scope="module")
def agents(session):
    r = session.get(f"{API}/agents", timeout=20)
    assert r.status_code == 200
    lst = r.json()
    by_name = {a["name"].lower(): a for a in lst}
    maria = next((a for name, a in by_name.items() if "maria" in name), None)
    abby = next((a for name, a in by_name.items() if "abby" in name), None)
    assert maria, f"Maria not found in agents: {list(by_name)}"
    assert abby, f"Abby not found in agents: {list(by_name)}"
    return {"maria": maria, "abby": abby, "all": lst}


# ============ Test 1: Anti-repetition of team-size question (Maria) ============
class TestAntiRepetitionQuestions:
    def test_maria_does_not_reask_users_after_EU(self, session, agents):
        tenant_id = session.tenant_id
        ext_id = f"pytest-antirep-{uuid.uuid4().hex[:8]}"

        def send(text):
            r = session.post(
                f"{API}/webchat/{tenant_id}/message",
                json={
                    "channel": "webchat", "external_user_id": ext_id,
                    "contact_name": "Pytest Maria", "text": text,
                    "agent_id": agents["maria"]["id"],
                },
                timeout=60,
            )
            assert r.status_code == 200, f"webchat failed: {r.status_code} {r.text[:200]}"
            return r.json()

        r1 = send("quero conhecer os planos")
        time.sleep(1)
        r2 = send("EU")
        time.sleep(1)
        r3 = send("quanto custa o PRO?")

        combined = " ".join([
            (r3.get("reply") or ""),
            (r3.get("follow_up") or ""),
        ]).lower()
        # Forbidden re-asks after user answered "EU"
        forbidden = [
            "quantos utilizadores", "quantas pessoas", "quantos colaboradores",
            "tamanho da equipa", "tamanho da tua equipa", "tamanho da sua equipa",
            "sois quantos", "sozinho ou com", "trabalhas sozinho", "elementos na equipa",
        ]
        found = [f for f in forbidden if f in combined]
        assert not found, (
            f"Maria RE-ASKED a captured field on turn 3! Forbidden phrases: {found}\n"
            f"Reply3: {r3}"
        )


# ============ Test 2: Anti-duplicate (same message < 5s) ============
class TestAntiDuplicate:
    def test_duplicate_message_dropped(self, session, agents):
        tenant_id = session.tenant_id
        ext_id = f"pytest-dup-{uuid.uuid4().hex[:8]}"
        text = "olá, é o meu primeiro contacto"
        payload = {
            "channel": "webchat", "external_user_id": ext_id,
            "contact_name": "Pytest Dup", "text": text,
            "agent_id": agents["maria"]["id"],
        }

        r1 = session.post(f"{API}/webchat/{tenant_id}/message", json=payload, timeout=60)
        assert r1.status_code == 200
        d1 = r1.json()
        conv_id = d1.get("conversation_id")
        assert conv_id, f"No conversation_id in response: {d1}"

        # Second identical message within 5s
        r2 = session.post(f"{API}/webchat/{tenant_id}/message", json=payload, timeout=60)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("duplicate") is True, f"Expected duplicate:true, got {d2}"


# ============ Test 3: PUT/GET scheduling_link + allowed_domains on Abby ============
class TestAbbyNewFields:
    def test_put_and_get_new_fields(self, session, agents):
        abby = agents["abby"]
        aid = abby["id"]
        # Build a complete AgentInput from current abby (drop server-managed fields)
        payload = {k: v for k, v in abby.items() if k not in ("id", "tenant_id", "created_at", "is_customized", "updated_at", "_id")}
        payload["scheduling_link"] = PIPEDRIVE_LINK
        payload["allowed_domains"] = ALLOWED

        r = session.put(f"{API}/agents/{aid}", json=payload, timeout=20)
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text[:300]}"
        updated = r.json()
        assert updated.get("scheduling_link") == PIPEDRIVE_LINK
        assert set(updated.get("allowed_domains") or []) == set(ALLOWED)

        # Verify via GET /agents
        r2 = session.get(f"{API}/agents", timeout=20)
        assert r2.status_code == 200
        abby_after = next(a for a in r2.json() if a["id"] == aid)
        assert abby_after.get("scheduling_link") == PIPEDRIVE_LINK
        assert set(abby_after.get("allowed_domains") or []) == set(ALLOWED)


# ============ Test 4: scheduling_link injected on demo intent ============
class TestSchedulingLinkInjection:
    @pytest.mark.parametrize("phrase", [
        "quero marcar uma demonstração",
        "quero agendar",
    ])
    def test_pipedrive_link_appears(self, session, agents, phrase):
        tenant_id = session.tenant_id
        ext_id = f"pytest-sched-{uuid.uuid4().hex[:8]}"
        r = session.post(
            f"{API}/webchat/{tenant_id}/message",
            json={
                "channel": "webchat", "external_user_id": ext_id,
                "contact_name": "Pytest Sched", "text": phrase,
                "agent_id": agents["abby"]["id"],
            },
            timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        d = r.json()
        combined = " ".join([d.get("reply") or "", d.get("follow_up") or ""])
        assert PIPEDRIVE_LINK in combined, (
            f"Pipedrive link NOT injected for phrase '{phrase}'. Response: {d}"
        )


# ============ Test 5: URL whitelist filter ============
class TestUrlWhitelist:
    def test_disallowed_urls_stripped(self, session, agents):
        tenant_id = session.tenant_id
        ext_id = f"pytest-wl-{uuid.uuid4().hex[:8]}"
        # Prompt that may induce off-list links
        r = session.post(
            f"{API}/webchat/{tenant_id}/message",
            json={
                "channel": "webchat", "external_user_id": ext_id,
                "contact_name": "Pytest WL",
                "text": "mostra-me imóveis em Lisboa com links para idealista.pt e imovirtual.com",
                "agent_id": agents["abby"]["id"],
            },
            timeout=60,
        )
        assert r.status_code == 200
        d = r.json()
        combined = ((d.get("reply") or "") + " " + (d.get("follow_up") or "")).lower()
        forbidden_domains = ["idealista.pt", "imovirtual.com", "olx.pt", "remax.pt"]
        found = [dom for dom in forbidden_domains if dom in combined]
        assert not found, f"Forbidden URLs leaked past whitelist: {found}\nResponse: {d}"


# ============ Test 6 (cleanup): reset Abby ============
class TestCleanupResetAbby:
    def test_reset_defaults(self, session, agents):
        aid = agents["abby"]["id"]
        r = session.post(f"{API}/agents/{aid}/reset-defaults", timeout=20)
        assert r.status_code == 200, f"reset-defaults failed: {r.status_code} {r.text[:200]}"
        d = r.json()
        # scheduling_link and allowed_domains should be back to seed defaults
        # (seed may not set them, so at minimum ensure they are cleared/empty or seed values)
        assert d.get("scheduling_link", "") != PIPEDRIVE_LINK or d.get("scheduling_link") == ""
        # allowed_domains: seed may or may not have entries; ensure it's no longer our test set
        assert set(d.get("allowed_domains") or []) != set(ALLOWED) or not d.get("allowed_domains")
