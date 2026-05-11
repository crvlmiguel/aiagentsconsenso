"""Tests for SSE streaming endpoint /api/webchat/{tenant_id}/stream (iter 11).

Validates:
  * 404 when tenant not found.
  * Error SSE event when agent_id missing/invalid (no 500).
  * Happy path: ready -> chunk(s) -> done sequence.
  * TTFT (time to first token, excluding the immediate 'ready') < 3.0s.
  * Persistence: user msg + AI msg saved to MongoDB after stream closes.
  * Regression: POST /api/webchat/{tid}/message still works.
"""
import json
import os
import time
import uuid

import httpx
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TENANT_ID = "b63f7593-d59a-491d-8c91-e28caea3f760"
MARIA_AGENT_ID = "4b4dbf03-2107-473a-b578-9456ad2a9318"


def _parse_sse_events(raw_lines):
    """Parse SSE 'data: {...}' lines into list of dicts."""
    events = []
    for line in raw_lines:
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            pass
    return events


# ---------- error paths ----------


def test_stream_404_tenant_not_found():
    r = requests.post(
        f"{BASE_URL}/api/webchat/00000000-0000-0000-0000-000000000000/stream",
        json={"text": "hi", "external_user_id": "TEST_x", "agent_id": MARIA_AGENT_ID},
        timeout=10,
    )
    assert r.status_code == 404
    body = r.json()
    assert "Tenant" in str(body) or "ão encontrado" in str(body)


def test_stream_error_event_when_agent_missing():
    r = requests.post(
        f"{BASE_URL}/api/webchat/{TENANT_ID}/stream",
        json={
            "text": "hi",
            "external_user_id": f"TEST_noagent_{uuid.uuid4().hex[:6]}",
            "agent_id": "00000000-0000-0000-0000-000000000000",
        },
        timeout=10,
        stream=True,
    )
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    events = _parse_sse_events(r.iter_lines(decode_unicode=True))
    assert any(e.get("type") == "error" for e in events), f"events={events}"


# ---------- happy path streaming ----------


def test_stream_happy_path_maria():
    """Open SSE, collect events, assert order ready -> chunk* -> done."""
    ext_id = f"TEST_stream_{uuid.uuid4().hex[:8]}"
    url = f"{BASE_URL}/api/webchat/{TENANT_ID}/stream"
    payload = {
        "text": "Olá Maria, podes apresentar-te brevemente?",
        "external_user_id": ext_id,
        "agent_id": MARIA_AGENT_ID,
        "contact_name": "Tester",
    }

    ttft = None
    t_start = time.time()
    events = []
    raw_event_types = []
    with httpx.stream("POST", url, json=payload, timeout=30.0) as r:
        assert r.status_code == 200, r.text
        assert "text/event-stream" in r.headers.get("content-type", "")
        # X-Accel-Buffering: 'no' is set by backend (may be stripped by Cloudflare).
        # We don't assert here because the CDN can remove hop-by-hop hints. The
        # critical evidence is that we actually receive chunks progressively
        # (which we measure via TTFT below).

        first_chunk_seen = False
        for line in r.iter_lines():
            if not line:
                continue
            if not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[len("data:") :].strip())
            except Exception:
                continue
            events.append(evt)
            raw_event_types.append(evt.get("type"))
            if evt.get("type") == "chunk" and not first_chunk_seen:
                ttft = time.time() - t_start
                first_chunk_seen = True
            if evt.get("type") == "done":
                break

    assert raw_event_types, "no SSE events received"
    assert raw_event_types[0] == "ready", f"first event was {raw_event_types[0]}, expected 'ready'"
    assert "done" in raw_event_types, f"missing 'done' event; got {raw_event_types}"
    # at least one chunk between ready and done
    assert any(t == "chunk" for t in raw_event_types), f"no 'chunk' events; got {raw_event_types}"

    done_evt = [e for e in events if e.get("type") == "done"][0]
    assert isinstance(done_evt.get("reply"), str) and len(done_evt["reply"]) > 0
    assert "conversation_id" in done_evt
    assert isinstance(done_evt.get("cards", []), list)

    # TTFT goal is <1.5s but be tolerant on public network
    assert ttft is not None, "never received a chunk"
    print(f"\n[TTFT] {ttft*1000:.0f}ms (goal <1500ms; tolerance <3000ms over public URL)")
    assert ttft < 3.0, f"TTFT too slow: {ttft:.2f}s"

    # Stash convo id for next test
    pytest.shared_conv = done_evt["conversation_id"]
    pytest.shared_ext_id = ext_id
    pytest.shared_full_reply = done_evt["reply"]


def test_stream_persists_messages_after_done():
    """After stream, the most recent conversation for that ext_id must contain
    the user message and the AI message."""
    ext_id = getattr(pytest, "shared_ext_id", None)
    conv_id = getattr(pytest, "shared_conv", None)
    if not ext_id or not conv_id:
        pytest.skip("happy-path test did not run first")

    # Give the background insert / DB write a moment
    time.sleep(1.0)

    # Use a known admin login to query convo (we don't have a direct read endpoint
    # without auth) — try the public webchat /message poll? We'll use the auth route.
    sess = requests.Session()
    login = sess.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "admin@consenso-agents.com", "password": "100%Consenso"},
        timeout=10,
    )
    if login.status_code != 200:
        pytest.skip(f"admin login failed ({login.status_code}); cannot verify persistence")
    token = login.json().get("token") or login.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    msgs = sess.get(
        f"{BASE_URL}/api/conversations/{conv_id}",
        headers=headers,
        timeout=10,
    )
    assert msgs.status_code == 200, msgs.text
    data = msgs.json().get("messages", [])
    senders = [m.get("sender") for m in data]
    assert "user" in senders, f"no user msg persisted: {senders}"
    assert "ai" in senders, f"no AI msg persisted: {senders}"
    ai_msgs = [m for m in data if m.get("sender") == "ai"]
    assert any(m.get("text") for m in ai_msgs), "AI message text empty"


# ---------- regression: non-streaming /message still works ----------


def test_message_endpoint_still_works():
    """Plain JSON /message endpoint should keep prior shape."""
    r = requests.post(
        f"{BASE_URL}/api/webchat/{TENANT_ID}/message",
        json={
            "text": "Olá Maria",
            "external_user_id": f"TEST_msg_{uuid.uuid4().hex[:8]}",
            "agent_id": MARIA_AGENT_ID,
            "contact_name": "Tester",
        },
        timeout=30,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "reply" in body and isinstance(body["reply"], str) and body["reply"]
    assert "conversation_id" in body
    # follow_up may be None or string
    assert "follow_up" in body
    assert "cards" in body


# ---------- regression: widget.js still serves __CP_ORIGIN__ replaced ----------


def test_widget_js_origin_injected():
    r = requests.get(f"{BASE_URL}/api/widget.js", timeout=10)
    assert r.status_code == 200
    body = r.text
    assert "__CP_ORIGIN__" not in body, "placeholder not replaced"
    # backend origin should appear somewhere
    backend_host = BASE_URL.split("//", 1)[1]
    assert backend_host in body
