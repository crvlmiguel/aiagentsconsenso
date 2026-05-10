"""Tests for Instagram Direct + Facebook Messenger channels.

Mirrors the WhatsApp Cloud verify+webhook+test-channel pattern.
Uses FAKE Meta tokens — Meta API will reject them, which proves wiring is correct."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TENANT_ID = "b63f7593-d59a-491d-8c91-e28caea3f760"
AGENT_MARIA = "4b4dbf03-2107-473a-b578-9456ad2a9318"

ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASSWORD = "100%Consenso"

FAKE_TOKEN = "EAAFAKE_TOKEN_FOR_TESTING"
FAKE_PAGE_ID = "1234567890"
FAKE_IG_USER_ID = "17841400000000000"
VERIFY_TOKEN = "test-verify-secret-2026"

AGENT_INPUT_FIELDS = [
    "name", "avatar_url", "welcome_message", "icebreakers", "tone", "goal",
    "system_prompt", "rules", "api_provider", "api_key", "model_provider",
    "model_name", "tools", "knowledge", "data_source_ids", "default_language",
    "notify_email", "channels", "email", "active",
]


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


def _fetch_agent(headers):
    r = requests.get(f"{BASE_URL}/api/agents", headers=headers, timeout=15)
    assert r.status_code == 200
    return next(a for a in r.json() if a["id"] == AGENT_MARIA)


def _put_channels(headers, agent: dict, channels: dict):
    payload = {k: agent.get(k) for k in AGENT_INPUT_FIELDS if agent.get(k) is not None}
    payload.setdefault("name", agent.get("name") or "Maria")
    payload["channels"] = channels
    return requests.put(
        f"{BASE_URL}/api/agents/{AGENT_MARIA}",
        json=payload, headers=headers, timeout=15,
    )


@pytest.fixture(scope="module")
def baseline(headers):
    """Yield (agent_doc, original_channels). Restore at end."""
    agent = _fetch_agent(headers)
    original = agent.get("channels") or {}
    yield agent, original
    _put_channels(headers, agent, original)


def _set_ig(headers, baseline, enabled=True, **overrides):
    agent, orig = baseline
    ch = {**orig, "instagram": {
        "enabled": enabled,
        "page_access_token": FAKE_TOKEN,
        "ig_user_id": FAKE_IG_USER_ID,
        "verify_token": VERIFY_TOKEN,
        **overrides,
    }}
    return _put_channels(headers, agent, ch)


def _set_fb(headers, baseline, enabled=True, **overrides):
    agent, orig = baseline
    ch = {**orig, "messenger": {
        "enabled": enabled,
        "page_access_token": FAKE_TOKEN,
        "page_id": FAKE_PAGE_ID,
        "verify_token": VERIFY_TOKEN,
        **overrides,
    }}
    return _put_channels(headers, agent, ch)


# ============== PUT /agents persistence ==============
class TestAgentChannelPersistence:
    def test_put_persists_instagram_and_messenger(self, headers, baseline):
        agent, orig = baseline
        new_channels = {
            **orig,
            "instagram": {"enabled": True, "page_access_token": FAKE_TOKEN,
                          "ig_user_id": FAKE_IG_USER_ID, "verify_token": VERIFY_TOKEN},
            "messenger": {"enabled": True, "page_access_token": FAKE_TOKEN,
                          "page_id": FAKE_PAGE_ID, "verify_token": VERIFY_TOKEN},
        }
        r = _put_channels(headers, agent, new_channels)
        assert r.status_code == 200, r.text[:300]

        fresh = _fetch_agent(headers)
        ig = fresh["channels"]["instagram"]
        fb = fresh["channels"]["messenger"]
        assert ig["enabled"] is True
        assert ig["ig_user_id"] == FAKE_IG_USER_ID
        assert ig["verify_token"] == VERIFY_TOKEN
        assert fb["enabled"] is True
        assert fb["page_id"] == FAKE_PAGE_ID
        assert fb["verify_token"] == VERIFY_TOKEN


# ============== Verify GET (Meta hub.challenge) ==============
class TestInstagramVerify:
    def test_verify_success(self, headers, baseline):
        r = _set_ig(headers, baseline, enabled=True)
        assert r.status_code == 200
        rv = requests.get(
            f"{BASE_URL}/api/webhooks/instagram/{TENANT_ID}/{AGENT_MARIA}",
            params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN,
                    "hub.challenge": "challenge-12345"},
            timeout=15,
        )
        assert rv.status_code == 200, rv.text[:200]
        assert rv.text == "challenge-12345"

    def test_verify_wrong_token_403(self, headers, baseline):
        _set_ig(headers, baseline, enabled=True)
        rv = requests.get(
            f"{BASE_URL}/api/webhooks/instagram/{TENANT_ID}/{AGENT_MARIA}",
            params={"hub.mode": "subscribe", "hub.verify_token": "wrong",
                    "hub.challenge": "x"},
            timeout=15,
        )
        assert rv.status_code == 403


class TestMessengerVerify:
    def test_verify_success(self, headers, baseline):
        r = _set_fb(headers, baseline, enabled=True)
        assert r.status_code == 200
        rv = requests.get(
            f"{BASE_URL}/api/webhooks/messenger/{TENANT_ID}/{AGENT_MARIA}",
            params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN,
                    "hub.challenge": "ch-9999"},
            timeout=15,
        )
        assert rv.status_code == 200
        assert rv.text == "ch-9999"

    def test_verify_wrong_token_403(self, headers, baseline):
        _set_fb(headers, baseline, enabled=True)
        rv = requests.get(
            f"{BASE_URL}/api/webhooks/messenger/{TENANT_ID}/{AGENT_MARIA}",
            params={"hub.mode": "subscribe", "hub.verify_token": "nope",
                    "hub.challenge": "x"},
            timeout=15,
        )
        assert rv.status_code == 403


# ============== POST inbound webhook ==============
class TestInstagramInbound:
    def test_disabled_returns_400(self, headers, baseline):
        agent, orig = baseline
        _put_channels(headers, agent, {**orig, "instagram": {"enabled": False}})
        r = requests.post(
            f"{BASE_URL}/api/webhooks/instagram/{TENANT_ID}/{AGENT_MARIA}",
            json={"object": "instagram", "entry": []}, timeout=15,
        )
        assert r.status_code == 400

    def test_enabled_processes_payload(self, headers, baseline):
        _set_ig(headers, baseline, enabled=True)
        payload = {
            "object": "instagram",
            "entry": [{"id": "ig", "messaging": [{
                "sender": {"id": "IGSID_TEST_42"},
                "recipient": {"id": FAKE_IG_USER_ID},
                "timestamp": 1700000000,
                "message": {"mid": "m1", "text": "Olá, tens T2 em Lisboa?"},
            }]}],
        }
        r = requests.post(
            f"{BASE_URL}/api/webhooks/instagram/{TENANT_ID}/{AGENT_MARIA}",
            json=payload, timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert isinstance(body.get("results"), list) and len(body["results"]) == 1
        assert body["results"][0]["sender"] == "IGSID_TEST_42"
        assert body["results"][0]["processed"] is True


class TestMessengerInbound:
    def test_disabled_returns_400(self, headers, baseline):
        agent, orig = baseline
        _put_channels(headers, agent, {**orig, "messenger": {"enabled": False}})
        r = requests.post(
            f"{BASE_URL}/api/webhooks/messenger/{TENANT_ID}/{AGENT_MARIA}",
            json={"object": "page", "entry": []}, timeout=15,
        )
        assert r.status_code == 400

    def test_enabled_processes_payload(self, headers, baseline):
        _set_fb(headers, baseline, enabled=True)
        payload = {
            "object": "page",
            "entry": [{"id": FAKE_PAGE_ID, "messaging": [{
                "sender": {"id": "PSID_TEST_77"},
                "recipient": {"id": FAKE_PAGE_ID},
                "timestamp": 1700000000,
                "message": {"mid": "fb1", "text": "Bom dia, queria visitar."},
            }]}],
        }
        r = requests.post(
            f"{BASE_URL}/api/webhooks/messenger/{TENANT_ID}/{AGENT_MARIA}",
            json=payload, timeout=60,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert len(body["results"]) == 1
        assert body["results"][0]["sender"] == "PSID_TEST_77"


# ============== test-channel endpoint ==============
class TestTestChannel:
    def test_instagram_disabled(self, headers, baseline):
        agent, orig = baseline
        _put_channels(headers, agent, {**orig, "instagram": {"enabled": False}})
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/instagram",
            headers=headers, timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False

    def test_instagram_fake_token_meta_rejects(self, headers, baseline):
        _set_ig(headers, baseline, enabled=True)
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/instagram",
            headers=headers, timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        err = (body.get("error") or "").lower()
        # Confirms we hit Graph API: error must be from Instagram label or about token/oauth/access
        assert "instagram:" in err or "oauth" in err or "token" in err or "access" in err, \
            f"unexpected error (should hit Graph): {body}"

    def test_messenger_disabled(self, headers, baseline):
        agent, orig = baseline
        _put_channels(headers, agent, {**orig, "messenger": {"enabled": False}})
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/messenger",
            headers=headers, timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["ok"] is False

    def test_messenger_fake_token_meta_rejects(self, headers, baseline):
        _set_fb(headers, baseline, enabled=True)
        r = requests.post(
            f"{BASE_URL}/api/agents/{AGENT_MARIA}/test-channel/messenger",
            headers=headers, timeout=20,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False
        err = (body.get("error") or "").lower()
        assert "messenger:" in err or "oauth" in err or "token" in err or "access" in err, \
            f"unexpected error (should hit Graph): {body}"


# ============== Regression — existing channels still work ==============
class TestRegressionWebchat:
    def test_webchat_message_returns_reply(self):
        r = requests.post(
            f"{BASE_URL}/api/webchat/{TENANT_ID}/message",
            json={
                "channel": "webchat",
                "external_user_id": "test-regression-001",
                "contact_name": "Tester",
                "text": "Olá",
                "agent_id": AGENT_MARIA,
            },
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        # Reply key may vary but some textual response is expected
        has_reply = any(k in body for k in ("reply", "text", "message", "answer"))
        assert has_reply, f"no reply key in {body.keys()}"
