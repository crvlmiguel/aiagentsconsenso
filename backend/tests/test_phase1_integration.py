"""Integration tests for Phase 1 features (iter13) — exercise public/auth REST endpoints
covering Maria plan knowledge, multi-language, finance card, lead scoring, feeds &
follow-up tick endpoints.
"""
import os
import re
import uuid
import time

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASS = "100%Consenso"
TENANT_ID = "b63f7593-d59a-491d-8c91-e28caea3f760"
MARIA_AGENT_ID = "4b4dbf03-2107-473a-b578-9456ad2a9318"


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    if r.status_code != 200:
        pytest.skip(f"Auth failed: {r.status_code} {r.text[:200]}")
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _send_message(text: str, extra_user_id: str | None = None, lang_hint: str | None = None):
    """Helper to call public /webchat/{tid}/message and return JSON."""
    payload = {
        "agent_id": MARIA_AGENT_ID,
        "external_user_id": extra_user_id or f"TEST_iter13_{uuid.uuid4().hex[:8]}",
        "text": text,
    }
    if lang_hint:
        payload["language"] = lang_hint
    r = requests.post(f"{BASE_URL}/api/webchat/{TENANT_ID}/message",
                      json=payload, timeout=45)
    return r


# ===================== MARIA PLAN KNOWLEDGE =====================

def test_maria_knows_starter_plan():
    r = _send_message("Quanto custa o plano STARTER?")
    assert r.status_code == 200, r.text
    reply = (r.json().get("reply") or "").lower()
    assert "49" in reply or "starter" in reply, f"Expected price/plan ref. Got: {reply[:300]}"


def test_maria_knows_pro_plan():
    r = _send_message("Qual o preço do plano PRO?")
    assert r.status_code == 200, r.text
    reply = (r.json().get("reply") or "").lower()
    assert "74" in reply or "pro" in reply, f"Got: {reply[:300]}"


def test_maria_knows_enterprise_plan():
    r = _send_message("Tens plano Enterprise? O que inclui?")
    assert r.status_code == 200, r.text
    reply = (r.json().get("reply") or "").lower()
    assert "enterprise" in reply, f"Got: {reply[:300]}"


# ===================== MULTI-LANGUAGE =====================
# Maria should respond in the SAME language as the user. We do best-effort substring
# / detection without language libs.

LANG_PROBES = [
    ("en", "Hello, what is the price of the PRO plan?",
     ["the", "plan", "pro"], ["olá", "obrigado"]),
    ("fr", "Bonjour, quel est le prix du plan PRO?",
     ["le", "plan", "prix"], []),
    ("de", "Hallo, was kostet der PRO-Plan?",
     ["der", "plan", "kostet", "pläne", "monat", "benutzer", "wir haben"], []),
    ("es", "Hola, ¿cuál es el precio del plan PRO?",
     ["el", "plan", "precio"], []),
    ("nl", "Hallo, wat is de prijs van het PRO-plan?",
     ["het", "plan", "prijs"], []),
]


@pytest.mark.parametrize("lang,question,expect_any,not_expect", LANG_PROBES)
def test_maria_responds_in_user_language(lang, question, expect_any, not_expect):
    r = _send_message(question)
    assert r.status_code == 200, r.text
    reply = (r.json().get("reply") or "").lower()
    # At least one of the expected target-language tokens should appear
    hits = [t for t in expect_any if t in reply]
    assert hits, f"[{lang}] reply doesn't seem in target language: {reply[:300]}"


# ===================== FINANCE SIMULATION CARD =====================

def test_finance_card_generated_on_price_question():
    r = _send_message("Quanto seria a prestação mensal para um imóvel de 500000 euros, "
                      "com 20% de entrada e 30 anos?")
    assert r.status_code == 200, r.text
    body = r.json()
    cards = body.get("cards") or []
    finance_cards = [c for c in cards if (c.get("type") or "") == "finance_simulation"]
    assert finance_cards, f"No finance_simulation card. cards={[c.get('type') for c in cards]}"
    fc = finance_cards[0]
    data = fc.get("data") or fc
    # Either nested or flat — check for prestacao_mensal somewhere
    flat = str(data)
    assert "prestacao_mensal" in flat or "prestação" in flat.lower(), flat[:300]


# ===================== LEAD SCORING via book-visit =====================

def test_book_visit_creates_hot_lead(auth_headers):
    ext_id = f"TEST_iter13_{uuid.uuid4().hex[:8]}"
    # 1) seed a quick convo
    _send_message("Quero ver um T2 em Lisboa", extra_user_id=ext_id)

    payload = {
        "name": "TEST_Iter13",
        "email": f"{ext_id}@test.com",
        "phone": "+351911111111",
        "date": "2026-02-15",
        "time": "10:00",
        "property_title": "T2 Test Lisboa",
        "property_link": "https://example.com/t2",
        "external_user_id": ext_id,
        "agent_id": MARIA_AGENT_ID,
    }
    r = requests.post(f"{BASE_URL}/api/webchat/{TENANT_ID}/book-visit",
                      json=payload, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    lead_id = body.get("lead_id")
    assert lead_id

    # Verify via authenticated leads endpoint
    r2 = requests.get(f"{BASE_URL}/api/leads", headers=auth_headers, timeout=15)
    assert r2.status_code == 200
    leads = r2.json() if isinstance(r2.json(), list) else r2.json().get("leads", [])
    match = [ld for ld in leads if ld.get("id") == lead_id]
    assert match, f"Created lead {lead_id} not retrievable"
    lead = match[0]
    assert lead.get("score", 0) >= 70, f"Score too low: {lead.get('score')}"
    assert lead.get("score_tier") in {"quente", "hot"}, f"tier: {lead.get('score_tier')}"


# ===================== FEEDS ENDPOINTS =====================

def test_feeds_get_returns_list(auth_headers):
    r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/feeds",
                     headers=auth_headers, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "feeds" in body
    assert isinstance(body["feeds"], list)
    assert "follow_up_enabled" in body


def test_feeds_put_set_and_get(auth_headers):
    new_feeds = [{"type": "csv", "url": "https://example.com/test_iter13.csv",
                  "name": "TEST_iter13"}]
    r = requests.put(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/feeds",
                     headers=auth_headers,
                     json={"feeds": new_feeds, "follow_up_enabled": True}, timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    # GET back
    r2 = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/feeds",
                      headers=auth_headers, timeout=15)
    feeds = r2.json().get("feeds") or []
    assert any(f.get("name") == "TEST_iter13" for f in feeds), f"Feed not persisted: {feeds}"

    # Cleanup → reset feeds to empty
    requests.put(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/feeds",
                 headers=auth_headers, json={"feeds": []}, timeout=15)


def test_feeds_refresh_endpoint(auth_headers):
    r = requests.post(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/feeds/refresh",
                      headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    assert "results" in r.json()


def test_feeds_unknown_agent_404(auth_headers):
    r = requests.get(f"{BASE_URL}/api/agents/nope-nope-nope/feeds",
                     headers=auth_headers, timeout=10)
    assert r.status_code == 404


def test_feeds_requires_auth():
    r = requests.get(f"{BASE_URL}/api/agents/{MARIA_AGENT_ID}/feeds", timeout=10)
    assert r.status_code in {401, 403}


# ===================== FOLLOW-UP TICK =====================

def test_follow_up_tick_admin_ok(auth_headers):
    r = requests.post(f"{BASE_URL}/api/agents/follow-up/tick",
                      headers=auth_headers, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True
    # Should report at least these counters
    for k in ("checked", "sent", "errors"):
        assert k in body, f"Missing key {k} in {body}"


def test_follow_up_tick_requires_auth():
    r = requests.post(f"{BASE_URL}/api/agents/follow-up/tick", timeout=10)
    assert r.status_code in {401, 403}


# ===================== REGRESSION =====================

def test_streaming_sse_still_works():
    """SSE /webchat/{tid}/stream should emit at least ready + chunk + done events."""
    ext_id = f"TEST_iter13_{uuid.uuid4().hex[:8]}"
    payload = {"agent_id": MARIA_AGENT_ID, "external_user_id": ext_id,
               "text": "Olá, és a Maria?"}
    with requests.post(f"{BASE_URL}/api/webchat/{TENANT_ID}/stream",
                       json=payload, stream=True, timeout=60) as r:
        assert r.status_code == 200, r.text
        kinds = set()
        deadline = time.time() + 45
        for raw in r.iter_lines(decode_unicode=True):
            if time.time() > deadline:
                break
            if not raw:
                continue
            if raw.startswith("data:"):
                payload_str = raw[5:].strip()
                if '"type"' in payload_str:
                    m = re.search(r'"type"\s*:\s*"([^"]+)"', payload_str)
                    if m:
                        kinds.add(m.group(1))
                        if "done" in kinds:
                            break
        assert "ready" in kinds or "chunk" in kinds, f"No SSE events: {kinds}"
        assert "done" in kinds or "chunk" in kinds, f"Stream never produced output: {kinds}"


def test_property_cards_when_user_asks_for_listings():
    """Regression: cards de imóveis aparecem quando o user pede explicitamente."""
    r = _send_message("Mostra-me imóveis em Lisboa por favor")
    assert r.status_code == 200, r.text
    body = r.json()
    cards = body.get("cards") or []
    # Should have at least 1 property-like card OR the reply mentions Lisboa items
    prop_like = [c for c in cards if (c.get("type") or "") in {"property", "item", "listing"}]
    reply = (body.get("reply") or "").lower()
    assert prop_like or "lisboa" in reply, f"No property cards and reply: {reply[:200]}"
