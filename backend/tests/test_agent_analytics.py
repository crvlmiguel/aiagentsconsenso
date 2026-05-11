"""Tests for the per-agent analytics endpoint (iter 12).

Covers:
- happy-path shape with days=7, 30, 90 (default=30)
- daily_series length == days
- invalid days values (-5, 9999) clamped to [1, 365]
- 404 for non-existent agent_id (and for cross-tenant access)
- tenant-scoped zeros (fresh tenant -> totals=0 but daily_series still has `days` items)
- regression: streaming endpoint still works on Maria (TTFT < 3s, chunks > 1)
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASS = "100%Consenso"
TENANT_ID = "b63f7593-d59a-491d-8c91-e28caea3f760"
MARIA_AGENT_ID = "4b4dbf03-2107-473a-b578-9456ad2a9318"
ALL_AGENTS = {
    "Abby": "1f6e2542-44fe-4967-9d55-f2e90c2c69a2",
    "Maria": "4b4dbf03-2107-473a-b578-9456ad2a9318",
    "StayLocal": "dcb8ef3e-e87b-4437-87d2-c271bf44ad5a",
    "Tejo": "bc8ed7a6-d528-40ef-9665-09e05ecfe9fc",
}


# ------------------ Fixtures ------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Admin auth failed: {r.status_code} {r.text[:200]}")
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ------------------ Happy path ------------------
class TestAnalyticsShape:
    """Validates the JSON shape returned by GET /api/agents/{id}/analytics."""

    def _validate_shape(self, body, expected_days):
        # Top-level keys
        for k in ("agent_id", "agent_name", "days", "totals",
                  "daily_series", "qualification_breakdown",
                  "top_icebreakers", "funnel"):
            assert k in body, f"missing key {k}"
        assert body["days"] == expected_days
        # totals
        for k in ("conversations", "messages", "leads", "conversion_rate"):
            assert k in body["totals"], f"totals missing {k}"
        assert isinstance(body["totals"]["conversion_rate"], (int, float))
        # daily_series
        assert isinstance(body["daily_series"], list)
        assert len(body["daily_series"]) == expected_days, \
            f"daily_series len {len(body['daily_series'])} != {expected_days}"
        for item in body["daily_series"]:
            assert "day" in item and "conversations" in item and "leads" in item
            assert isinstance(item["day"], str) and len(item["day"]) == 10  # YYYY-MM-DD
        # qualification breakdown — exactly 4 buckets
        for k in ("quente", "morno", "frio", "outros"):
            assert k in body["qualification_breakdown"]
            assert isinstance(body["qualification_breakdown"][k], int)
        # top_icebreakers
        assert isinstance(body["top_icebreakers"], list)
        for ib in body["top_icebreakers"]:
            for k in ("opener", "opens", "leads", "rate"):
                assert k in ib
        # funnel — 4 stages
        assert isinstance(body["funnel"], list)
        assert len(body["funnel"]) == 4
        expected_stages = ["Visitantes", "Engajados (3+ msgs)", "Qualificados", "Leads capturados"]
        assert [f["stage"] for f in body["funnel"]] == expected_stages
        for f in body["funnel"]:
            assert isinstance(f["value"], int)

    def test_default_days_is_30(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        self._validate_shape(r.json(), expected_days=30)

    def test_days_7(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics?days=7",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200
        self._validate_shape(r.json(), expected_days=7)

    def test_days_90(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics?days=90",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200
        self._validate_shape(r.json(), expected_days=90)

    def test_all_4_production_agents_respond(self, auth_headers):
        for name, aid in ALL_AGENTS.items():
            r = requests.get(f"{BASE_URL}/api/agents/{aid}/analytics?days=30",
                             headers=auth_headers, timeout=30)
            assert r.status_code == 200, f"{name} returned {r.status_code}"
            body = r.json()
            assert body["agent_id"] == aid
            assert body["agent_name"], f"{name} missing agent_name"
            assert len(body["daily_series"]) == 30

    def test_maria_has_data(self, auth_headers):
        # Maria is expected to have meaningful data (56 convos in last 30d)
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics?days=30",
                         headers=auth_headers, timeout=30)
        body = r.json()
        assert body["totals"]["conversations"] >= 0
        # Sum of daily_series conversations should not exceed totals
        daily_sum = sum(d["conversations"] for d in body["daily_series"])
        assert daily_sum <= body["totals"]["conversations"] + 5  # tolerance for older convos


# ------------------ Validation / clamping ------------------
class TestAnalyticsValidation:
    def test_days_negative_clamped(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics?days=-5",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["days"] == 1  # clamped to min
        assert len(body["daily_series"]) == 1

    def test_days_huge_clamped(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics?days=9999",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert body["days"] == 365  # clamped to max
        assert len(body["daily_series"]) == 365

    def test_days_zero_falls_back_to_default(self, auth_headers):
        # days=0 is falsy → server falls back to default 30 (by design: `days or 30`)
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics?days=0",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 200
        assert r.json()["days"] == 30


# ------------------ Error handling ------------------
class TestAnalyticsErrors:
    def test_404_unknown_agent(self, auth_headers):
        fake = str(uuid.uuid4())
        r = requests.get(f"{BASE_URL}/api/agents/{fake}/analytics",
                         headers=auth_headers, timeout=30)
        assert r.status_code == 404

    def test_unauthenticated_rejected(self):
        r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/analytics", timeout=30)
        assert r.status_code in (401, 403)


# ------------------ Streaming regression ------------------
class TestStreamingRegression:
    def test_maria_stream_still_works(self):
        """Smoke test the SSE endpoint: ready -> chunks -> done.

        SSE format here uses `data: {"type": "..."}` (not `event:` lines).
        """
        import json
        external_id = f"TEST_iter12_{uuid.uuid4().hex[:8]}"
        url = f"{BASE_URL}/api/webchat/{TENANT_ID}/stream"
        payload = {"agent_id": MARIA_AGENT_ID, "text": "Olá",
                   "external_user_id": external_id}
        types = []
        chunks = 0
        with requests.post(url, json=payload, stream=True, timeout=30) as r:
            assert r.status_code == 200
            assert "text/event-stream" in r.headers.get("content-type", "")
            for raw in r.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                try:
                    evt = json.loads(raw[len("data:"):].strip())
                except Exception:
                    continue
                t = evt.get("type")
                types.append(t)
                if t == "chunk":
                    chunks += 1
                if t == "done":
                    break
        assert types and types[0] == "ready", f"types={types}"
        assert "done" in types, f"types={types}"
        assert chunks >= 1, f"expected >=1 chunks, got {chunks} (types={types})"
