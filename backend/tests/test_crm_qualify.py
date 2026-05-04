"""CRM Qualification + Auth migration tests (iteration 8)."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or "https://business-os-hub-3.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")

ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASSWORD = "100%Consenso"
DEMO_EMAIL = "demo@consenso-agents.com"
DEMO_PASSWORD = "demo1234"

FUNNEL_STATES = {"novo", "qualificando", "qualificado", "credito_simulado", "visita_agendada"}
BANNED_TAGS = {"sales", "general", "support", "billing", "high", "urgent", "technical", "other"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"no token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------- Auth migration ----------
class TestAuthMigration:
    def test_new_admin_login_ok(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("access_token") or r.json().get("token")

    def test_new_demo_login_ok(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}, timeout=30)
        assert r.status_code == 200

    def test_old_admin_email_rejected(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "admin@consensoplus.com", "password": "100%Consenso"}, timeout=30)
        assert r.status_code == 401, f"expected 401 for old admin email, got {r.status_code}"

    def test_old_demo_email_rejected(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "demo@consenso.plus", "password": "demo1234"}, timeout=30)
        assert r.status_code == 401, f"expected 401 for old demo email, got {r.status_code}"


# ---------- Conversations listing ----------
class TestConversationsListing:
    def test_list_conversations(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        # Expect a list (possibly wrapped)
        items = data if isinstance(data, list) else (data.get("items") or data.get("conversations") or [])
        assert isinstance(items, list)
        assert len(items) >= 1, "ABBI tenant must have seeded conversations"
        # Every convo must have qualification after backfill
        missing = [c.get("id") for c in items if not c.get("qualification")]
        assert not missing, f"conversations without qualification: {missing}"
        # Tags must be subset of qualification.tags (no legacy generic tags)
        legacy_leak = []
        for c in items:
            qtags = set((c.get("qualification") or {}).get("tags") or [])
            ctags = set(c.get("tags") or [])
            for t in ctags:
                if t.lower() in BANNED_TAGS:
                    legacy_leak.append((c.get("id"), t))
        assert not legacy_leak, f"legacy/banned tags leaked: {legacy_leak}"


# ---------- Qualify endpoint ----------
class TestQualifyEndpoint:
    @pytest.fixture(scope="class")
    def a_conv_id(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers, timeout=30)
        items = r.json() if isinstance(r.json(), list) else (r.json().get("items") or [])
        assert items, "no conversations to test qualify on"
        return items[0]["id"]

    def test_qualify_endpoint_returns_200_and_schema(self, auth_headers, a_conv_id):
        r = requests.post(f"{BASE_URL}/api/conversations/{a_conv_id}/qualify",
                          headers=auth_headers, timeout=90)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("ok") is True
        q = body.get("qualification")
        assert isinstance(q, dict)
        # Required fields
        for key in ("status", "lead", "search", "budget", "profile", "tags", "summary"):
            assert key in q, f"missing key {key} in qualification: {q}"
        assert q["status"] in FUNNEL_STATES, f"invalid status: {q['status']}"
        assert isinstance(q["lead"], dict) and set(q["lead"].keys()) >= {"name", "email"}
        assert isinstance(q["search"], dict) and set(q["search"].keys()) >= {"property_type", "zone"}
        assert isinstance(q["tags"], list)
        assert len(q["tags"]) <= 5, "tags must be max 5"
        # No duplicates (case-insensitive)
        lowers = [t.lower() for t in q["tags"] if isinstance(t, str)]
        assert len(lowers) == len(set(lowers)), f"duplicate tags: {q['tags']}"
        # No banned generic tags
        leaked = [t for t in q["tags"] if isinstance(t, str) and t.lower() in BANNED_TAGS]
        assert not leaked, f"banned tags in output: {leaked}"
        assert isinstance(q["summary"], str)

    def test_qualify_persisted_in_conversation(self, auth_headers, a_conv_id):
        # Already qualified above; GET and check persistence
        r = requests.get(f"{BASE_URL}/api/conversations", headers=auth_headers, timeout=30)
        items = r.json() if isinstance(r.json(), list) else (r.json().get("items") or [])
        target = next((c for c in items if c["id"] == a_conv_id), None)
        assert target is not None
        q = target.get("qualification")
        assert q and q.get("status") in FUNNEL_STATES
        # conversation.tags mirror qualification.tags
        assert set(target.get("tags") or []) == set(q.get("tags") or []), \
            f"conversation.tags != qualification.tags (convo={target.get('tags')} qual={q.get('tags')})"

    def test_qualify_unknown_conv_404(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/conversations/zzz-unknown-conv-id/qualify",
                          headers=auth_headers, timeout=30)
        assert r.status_code == 404

    def test_qualify_requires_auth(self):
        r = requests.post(f"{BASE_URL}/api/conversations/any/qualify", timeout=15)
        assert r.status_code in (401, 403)


# ---------- Normalize unit test (import engine) ----------
class TestNormalizeFallback:
    def test_invalid_status_falls_back_to_novo(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from ai.qualify import _normalize
        out = _normalize({"status": "bogus", "tags": ["sales", "general", "T3", "T3", "Braga"]})
        assert out["status"] == "novo"
        assert "sales" not in [t.lower() for t in out["tags"]]
        assert "general" not in [t.lower() for t in out["tags"]]
        # de-duped
        lowers = [t.lower() for t in out["tags"]]
        assert len(lowers) == len(set(lowers))

    def test_status_as_tag_is_stripped(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from ai.qualify import _normalize
        out = _normalize({"status": "qualificado", "tags": ["qualificado", "T2"]})
        assert "qualificado" not in [t.lower() for t in out["tags"]]
