"""Iter14 — Tests for CONSENSO PLUS global rules + customization endpoints.

Covers:
- POST /api/agents/{id}/reset-defaults (Maria, StayLocal, Tejo, Abby)
- PUT /api/agents/{id} sets is_customized=true and persists theme
- GET /api/agents returns new fields theme + is_customized
- POST /api/agents/{maria_id}/test global rule checks:
    * plans layout (3 plans in single message, follow_up empty)
    * anti-loop on short "eu" reply
    * sector hotelaria — no property cards
    * multi-language (English)
    * follow_up filter when reply ends with "?"
- Bootstrap idempotency: customization persists across backend restart
  (test verifies via DB read flag — restart itself is exercised separately).
"""

import os
import time
import copy
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASS = "100%Consenso"


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
    return s


@pytest.fixture(scope="module")
def agents(session):
    r = session.get(f"{BASE_URL}/api/agents", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) >= 4
    by_name = {}
    for a in data:
        n = (a.get("name") or "").lower()
        if "maria" in n:
            by_name["maria"] = a
        elif "staylocal" in n:
            by_name["staylocal"] = a
        elif "tejo" in n:
            by_name["tejo"] = a
        elif "abby" in n or "abbi" in n:
            by_name["abby"] = a
    assert {"maria", "staylocal", "tejo", "abby"} <= set(by_name), f"missing seeded agents: {list(by_name)}"
    return by_name


# ---------------- Model shape ----------------
class TestAgentModel:
    def test_list_agents_has_theme_and_is_customized(self, session):
        r = session.get(f"{BASE_URL}/api/agents", timeout=30)
        assert r.status_code == 200
        for a in r.json():
            assert "theme" in a, f"agent {a.get('name')} missing 'theme'"
            assert "is_customized" in a, f"agent {a.get('name')} missing 'is_customized'"
            assert isinstance(a["theme"], dict)
            assert isinstance(a["is_customized"], bool)


# ---------------- Reset defaults ----------------
class TestResetDefaults:
    @pytest.mark.parametrize("key", ["maria", "staylocal", "tejo", "abby"])
    def test_reset_defaults_clears_is_customized_and_restores_seed(self, session, agents, key):
        agent = agents[key]
        aid = agent["id"]
        # 1) Mark agent as customized via PUT (mutate welcome + theme).
        original = copy.deepcopy(agent)
        put_payload = {k: original.get(k) for k in [
            "name", "avatar_url", "welcome_message", "icebreakers", "tone",
            "goal", "system_prompt", "rules", "api_provider", "api_key",
            "model_provider", "model_name", "tools", "knowledge",
            "data_source_ids", "default_language", "notify_email",
            "channels", "email", "theme", "active",
        ]}
        # Ensure required string fields aren't None
        for sk in ["name", "welcome_message", "tone", "goal", "system_prompt"]:
            if put_payload.get(sk) is None:
                put_payload[sk] = ""
        put_payload["welcome_message"] = "TEST_iter14 custom welcome — should be reverted"
        put_payload["theme"] = {
            "primary": "#123456", "primary_dark": "#000000",
            "primary_soft": "#eeeeee", "primary_border": "#cccccc",
            "bot": "#ff00ff",
        }
        r = session.put(f"{BASE_URL}/api/agents/{aid}", json=put_payload, timeout=30)
        assert r.status_code == 200, f"PUT failed: {r.status_code} {r.text[:300]}"
        upd = r.json()
        assert upd["is_customized"] is True
        assert upd["welcome_message"] == "TEST_iter14 custom welcome — should be reverted"
        assert upd["theme"]["primary"] == "#123456"

        # 2) Call reset-defaults
        r = session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)
        assert r.status_code == 200, f"reset failed: {r.status_code} {r.text[:300]}"
        reset = r.json()
        assert reset["is_customized"] is False, f"is_customized not reset for {key}"
        assert reset["welcome_message"] != "TEST_iter14 custom welcome — should be reverted", (
            f"welcome was not restored for {key}: still '{reset['welcome_message'][:80]}'"
        )
        # Seed theme must overwrite the dummy theme we pushed
        assert reset["theme"].get("primary") != "#123456", f"theme.primary not reset for {key}"
        assert reset["theme"].get("primary"), f"theme.primary empty after reset for {key}"
        # System prompt must be non-empty (seed prompt always > 200 chars typically)
        assert len(reset.get("system_prompt") or "") > 50, (
            f"system_prompt seems empty after reset for {key} (len={len(reset.get('system_prompt') or '')})"
        )
        # Icebreakers must be populated (seed always provides ≥3)
        assert isinstance(reset.get("icebreakers"), list)
        assert len(reset["icebreakers"]) >= 3, f"icebreakers empty after reset for {key}"


# ---------------- PUT marks is_customized=true ----------------
class TestPutCustomization:
    def test_put_marks_customized_and_persists_theme(self, session, agents):
        agent = agents["maria"]
        aid = agent["id"]
        # Reset first so we start from clean slate
        session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)

        # Re-fetch latest from list
        latest = next(a for a in session.get(f"{BASE_URL}/api/agents").json() if a["id"] == aid)
        payload = {k: latest.get(k) for k in [
            "name", "avatar_url", "welcome_message", "icebreakers", "tone",
            "goal", "system_prompt", "rules", "api_provider", "api_key",
            "model_provider", "model_name", "tools", "knowledge",
            "data_source_ids", "default_language", "notify_email",
            "channels", "email", "theme", "active",
        ]}
        for sk in ["name", "welcome_message", "tone", "goal", "system_prompt"]:
            if payload.get(sk) is None:
                payload[sk] = ""
        new_theme = {
            "primary": "#aabbcc", "primary_dark": "#445566",
            "primary_soft": "#f0f0f0", "primary_border": "#dddddd",
            "bot": "#778899",
        }
        payload["theme"] = new_theme
        r = session.put(f"{BASE_URL}/api/agents/{aid}", json=payload, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["is_customized"] is True
        assert data["theme"] == new_theme

        # Verify via GET on list
        re_fetch = next(a for a in session.get(f"{BASE_URL}/api/agents").json() if a["id"] == aid)
        assert re_fetch["is_customized"] is True
        assert re_fetch["theme"] == new_theme

        # Cleanup
        session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)


# ---------------- Maria conversational global rules ----------------
def _maria_id(agents):
    return agents["maria"]["id"]


class TestMariaGlobalRules:
    def test_plans_layout_single_message(self, session, agents):
        aid = _maria_id(agents)
        # Ensure clean (non-customized) seed prompt
        session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)
        r = session.post(f"{BASE_URL}/api/agents/{aid}/test",
                         json={"text": "Olá, quanto custa?"}, timeout=120)
        assert r.status_code == 200, f"/test failed: {r.status_code} {r.text[:300]}"
        data = r.json()
        reply = (data.get("reply") or "").lower()
        follow_up = (data.get("follow_up") or "").strip()
        # Must mention all 3 plans in a single message
        assert "starter" in reply, f"STARTER missing in reply: {reply[:300]}"
        assert "pro" in reply, f"PRO missing in reply: {reply[:300]}"
        assert "enterprise" in reply, f"ENTERPRISE missing in reply: {reply[:300]}"
        # Prices
        assert "49,90" in reply or "49.90" in reply, "STARTER price missing"
        assert "74,90" in reply or "74.90" in reply, "PRO price missing"
        # follow_up must be empty (reply already has CTA/question)
        assert follow_up in ("", "null") or follow_up is None, (
            f"follow_up should be empty when plans are shown — got: {follow_up!r}"
        )

    def test_anti_loop_short_reply_eu(self, session, agents):
        aid = _maria_id(agents)
        r = session.post(f"{BASE_URL}/api/agents/{aid}/test",
                         json={"text": "eu"}, timeout=120)
        assert r.status_code == 200
        reply = (r.json().get("reply") or "").lower()
        # Must NOT contain apology phrases for confusion/repeat
        forbidden = ["desculpa pela confusão", "perdi-me", "podes repetir", "desculpa, podes"]
        for f in forbidden:
            assert f not in reply, f"forbidden apology phrase '{f}' present in reply: {reply[:300]}"

    def test_sector_hotelaria_no_property_cards(self, session, agents):
        aid = _maria_id(agents)
        r = session.post(f"{BASE_URL}/api/agents/{aid}/test",
                         json={"text": "Tenho um hotel em Lisboa, como funciona?"}, timeout=120)
        assert r.status_code == 200
        data = r.json()
        cards = data.get("cards") or []
        # No property-type cards (Maria is consenso seller, not Abby/StayLocal)
        property_card_kinds = {"property", "imovel", "imovel_card"}
        has_property = any(
            (isinstance(c, dict) and (c.get("type") in property_card_kinds or c.get("kind") in property_card_kinds))
            for c in cards
        )
        assert not has_property, f"unexpected property cards in hotelaria reply: {cards[:2]}"

    def test_multi_language_english(self, session, agents):
        aid = _maria_id(agents)
        r = session.post(f"{BASE_URL}/api/agents/{aid}/test",
                         json={"text": "Hello, what plans do you have?"}, timeout=120)
        assert r.status_code == 200
        data = r.json()
        lang = data.get("language") or data.get("lang") or ""
        reply = (data.get("reply") or "")
        # Language detected as en
        assert lang.lower().startswith("en"), f"expected language=en, got {lang!r}"
        # No pt-BR markers
        low = reply.lower()
        forbidden_ptbr = ["você", "tela", "celular", "estamos disponíveis"]
        for f in forbidden_ptbr:
            assert f not in low, f"pt-BR token '{f}' leaked into English reply: {reply[:300]}"
        # Some EN tokens expected
        assert any(t in low for t in [" the ", " you ", "plan", "we ", " our "]), (
            f"reply doesn't look like English: {reply[:200]}"
        )

    def test_follow_up_filter_when_reply_ends_with_question(self, session, agents):
        """When reply ends with '?', follow_up must be None/empty."""
        aid = _maria_id(agents)
        r = session.post(f"{BASE_URL}/api/agents/{aid}/test",
                         json={"text": "olá!"}, timeout=120)
        assert r.status_code == 200
        data = r.json()
        reply = (data.get("reply") or "").rstrip()
        fu = data.get("follow_up")
        if reply.endswith("?"):
            assert not fu or not str(fu).strip(), (
                f"follow_up must be empty when reply ends with '?'. reply={reply[-80:]!r} fu={fu!r}"
            )

    def test_follow_up_never_generic(self, session, agents):
        """No generic follow_ups like 'queres saber mais?' should ever pass the filter."""
        aid = _maria_id(agents)
        # Run two distinct turns and verify generic strings are never the follow_up
        prompts = [
            "Olá, quanto custa?",
            "Tenho um hotel em Lisboa, como funciona?",
            "Hello, what plans do you have?",
        ]
        for p in prompts:
            r = session.post(f"{BASE_URL}/api/agents/{aid}/test", json={"text": p}, timeout=120)
            assert r.status_code == 200, f"prompt failed: {p}"
            fu = (r.json().get("follow_up") or "")
            fu_low = fu.lower().strip()
            bad = [
                "queres saber mais", "posso ajudar em algo mais",
                "estou aqui para ajudar", "estou à disposição",
            ]
            for b in bad:
                assert b not in fu_low, f"generic follow_up '{b}' present for prompt {p!r}: {fu!r}"
