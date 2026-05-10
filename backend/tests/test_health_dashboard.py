"""Iteration 10 — Channel Health Dashboard tests.

Covers:
- GET /api/agents/health (shape, channels, configured flag, persistence reflection)
- POST /api/agents/{id}/test-channel/{channel} persists last_test_* on the agent
- Telegram regression with bad token still works through the new _run_channel_test

Uses FAKE Telegram token to avoid hitting any real provider successfully.
The fixture restores Maria's telegram channel state (enabled=False) on teardown.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASSWORD = "100%Consenso"

AGENT_MARIA = "4b4dbf03-2107-473a-b578-9456ad2a9318"
FAKE_TG_TOKEN = "INVALID:TOKEN"

AGENT_INPUT_FIELDS = [
    "name", "avatar_url", "welcome_message", "icebreakers", "tone", "goal",
    "system_prompt", "rules", "api_provider", "api_key", "model_provider",
    "model_name", "tools", "knowledge", "data_source_ids", "default_language",
    "notify_email", "channels", "email", "active",
]

EXPECTED_CHANNELS = {"webchat", "whatsapp", "telegram", "instagram", "messenger"}


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed {r.status_code}: {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


def _fetch_maria(headers):
    r = requests.get(f"{BASE_URL}/api/agents", headers=headers, timeout=15)
    assert r.status_code == 200, r.text
    return next(a for a in r.json() if a["id"] == AGENT_MARIA)


def _put_agent(headers, agent: dict, channels: dict):
    payload = {k: agent.get(k) for k in AGENT_INPUT_FIELDS if agent.get(k) is not None}
    payload.setdefault("name", agent.get("name") or "Maria")
    payload["channels"] = channels
    return requests.put(
        f"{BASE_URL}/api/agents/{AGENT_MARIA}",
        json=payload, headers=headers, timeout=15,
    )


@pytest.fixture(scope="module")
def maria_telegram_enabled(headers):
    """Enable telegram on Maria with a FAKE token; restore enabled=False at teardown."""
    agent = _fetch_maria(headers)
    original = (agent.get("channels") or {}).copy()
    chs = {**original}
    tg = dict(chs.get("telegram") or {})
    tg["enabled"] = True
    tg["bot_token"] = FAKE_TG_TOKEN
    chs["telegram"] = tg
    r = _put_agent(headers, agent, chs)
    assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text[:300]}"
    yield
    # teardown — restore enabled=False, drop fake token
    agent2 = _fetch_maria(headers)
    chs2 = (agent2.get("channels") or {}).copy()
    tg2 = dict(chs2.get("telegram") or {})
    tg2["enabled"] = False
    tg2["bot_token"] = ""
    chs2["telegram"] = tg2
    _put_agent(headers, agent2, chs2)


# ---------------- GET /api/agents/health ----------------
class TestAgentsHealth:
    def test_unauthenticated_blocked(self):
        r = requests.get(f"{BASE_URL}/api/agents/health", timeout=15)
        assert r.status_code in (401, 403), f"unexpected: {r.status_code}"

    def test_health_returns_list_with_5_channels_each(self, headers):
        r = requests.get(f"{BASE_URL}/api/agents/health", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "expected at least one active agent"
        for agent in data:
            assert "id" in agent and "name" in agent
            assert "channels" in agent and isinstance(agent["channels"], list)
            chs = {c["channel"] for c in agent["channels"]}
            assert chs == EXPECTED_CHANNELS, (
                f"agent {agent['name']} channels mismatch: {chs}"
            )
            for c in agent["channels"]:
                for k in ("enabled", "configured", "last_test_at",
                          "last_test_ok", "last_test_info", "last_test_error"):
                    assert k in c, f"missing key {k} in {c}"
                assert isinstance(c["enabled"], bool)
                assert isinstance(c["configured"], bool)

    def test_webchat_is_always_configured(self, headers):
        r = requests.get(f"{BASE_URL}/api/agents/health", headers=headers, timeout=15)
        data = r.json()
        for agent in data:
            wc = next(c for c in agent["channels"] if c["channel"] == "webchat")
            assert wc["configured"] is True

    def test_health_excludes_mongo_id(self, headers):
        r = requests.get(f"{BASE_URL}/api/agents/health", headers=headers, timeout=15)
        for agent in r.json():
            assert "_id" not in agent


# ---------------- POST /test-channel persists state ----------------
class TestTestChannelPersistence:
    def test_telegram_bad_token_persists_failure(self, headers, maria_telegram_enabled):
        # POST /test-channel/telegram — should hit Telegram, get rejected
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/telegram",
            headers=headers, timeout=20,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("ok") is False
        # Telegram-specific error shape (regression — _run_channel_test refactor)
        assert "Telegram" in (body.get("error") or "") or "Token" in (body.get("error") or "")

        # Now GET /agents/health — last_test_* should be persisted
        time.sleep(0.5)  # tiny window for write to land
        h = requests.get(f"{BASE_URL}/api/agents/health", headers=headers, timeout=15)
        assert h.status_code == 200
        agent = next(a for a in h.json() if a["id"] == AGENT_MARIA)
        tg = next(c for c in agent["channels"] if c["channel"] == "telegram")
        assert tg["enabled"] is True
        assert tg["configured"] is True  # bot_token is set (even if fake)
        assert tg["last_test_at"], "last_test_at should be persisted"
        assert tg["last_test_ok"] is False
        assert tg["last_test_error"], "last_test_error should be persisted"

    def test_test_channel_disabled_returns_error(self, headers):
        # whatsapp on Maria is disabled by default — should return error, not crash
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/whatsapp",
            headers=headers, timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is False
        assert "desativado" in (body.get("error") or "").lower() or "Ative" in (body.get("error") or "")

    def test_test_channel_unknown_channel(self, headers):
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/foobar",
            headers=headers, timeout=15,
        )
        # endpoint must respond (either via "Canal desativado" since not enabled,
        # or "Canal não suportado") — never 500
        assert r.status_code == 200
        assert r.json().get("ok") is False


# ---------------- Regression: webchat + dashboard stats still OK ----------------
class TestRegression:
    def test_dashboard_stats_still_works(self, headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=headers, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("conversations", "messages", "leads"):
            assert k in d

    def test_widget_js_cross_domain_marker(self):
        # No auth needed for /api/widget.js
        r = requests.get(f"{BASE_URL}/api/widget.js", timeout=15)
        assert r.status_code == 200
        assert "__CP_ORIGIN__" in r.text or "CP_ORIGIN" in r.text
