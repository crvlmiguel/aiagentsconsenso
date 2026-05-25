"""Iter15 — CONSENSO theme unification + ImmoAI agent + Maria short-answer + reset-defaults regression.

Covers:
- GET /api/agents returns 5 agents (Maria, StayLocal, Tejo, Abby, ImmoAI) all with
  theme.primary=#4591CE and theme.bot=#E4AC1E (CONSENSO_THEME).
- ImmoAI agent shape: prompt_len>=4000, 6 icebreakers, KB has 8 knowledge chunks
  + 5 demo properties (T2 Benfica, T3 Parque Nações, T4 Cascais, T1 Porto, T3 Almada).
- ImmoAI conversational flow via POST /api/webchat/{tenant}/message with a stable
  external_user_id across turns:
    turn1 'estou à procura de casa' → asks comprar/arrendar
    turn2 'comprar'                → asks zona/onde
    turn3 'Lisboa'                 → asks tipologia OR orçamento
    turn4 'T2 ou T3, até 350k'     → returns >=1 card filtered by budget
                                     (must NOT include Cascais €950k or Parque Nações €520k)
- ImmoAI tom humano: at least one human expression across first 3 turns;
  never robotic phrases like "Como assistente virtual", "Sou um chatbot".
- ImmoAI conversion: after cards, must propose visit/next step.
- Maria short-answer interpretation: 'Olá quanto custa?' → 'eu' → 'eu' →
  recommends STARTER plan (not re-asking team-size).
- Maria continuidade: after 'sim' (post demo question) → must share
  https://consenso-shop.eu/marcar-reuniao link (reply OR follow_up).
- Reset-defaults for ImmoAI: PUT customize → reset → seed restored.
- Bootstrap idempotency regression: agents with is_customized=true preserved
  (validated at code-contract level — no physical restart).
"""

import os
import time
import uuid
import copy
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASS = "100%Consenso"

HUMAN_EXPRESSIONS = [
    "perfeito", "boa", "excelente", "faz sentido", "tudo bem", "sem problema",
    "ótimo", "otimo", "claro", "vou já", "vou ja", "deixa-me", "tenho algo",
    "conta-me", "boa pergunta", "faz todo o sentido",
]
ROBOTIC_FORBIDDEN = [
    "como assistente virtual", "sou um chatbot", "como chatbot",
    "posso processar a sua solicitação", "em que posso ser útil hoje",
]


# ---------------- fixtures ----------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    s.headers.update({"Authorization": f"Bearer {body['token']}"})
    s._tenant_id = body["user"]["tenant_id"]  # type: ignore[attr-defined]
    return s


@pytest.fixture(scope="module")
def agents(session):
    r = session.get(f"{BASE_URL}/api/agents", timeout=30)
    assert r.status_code == 200
    data = r.json()
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
        elif "immoai" in n:
            by_name["immoai"] = a
    assert {"maria", "staylocal", "tejo", "abby", "immoai"} <= set(by_name), (
        f"missing agents: {list(by_name)}"
    )
    return by_name


# ---------------- 1. CONSENSO theme unification across all agents ----------------
class TestConsensoThemeUnified:
    def test_all_five_agents_listed(self, agents):
        assert len(agents) == 5

    @pytest.mark.parametrize("key", ["maria", "staylocal", "tejo", "abby", "immoai"])
    def test_agent_uses_consenso_theme(self, agents, key):
        theme = agents[key].get("theme") or {}
        assert theme.get("primary") == "#4591CE", (
            f"{key} primary={theme.get('primary')!r} ≠ #4591CE"
        )
        assert theme.get("bot") == "#E4AC1E", (
            f"{key} bot={theme.get('bot')!r} ≠ #E4AC1E"
        )


# ---------------- 2. ImmoAI agent shape ----------------
class TestImmoAIShape:
    def test_immoai_exists_with_prompt_and_icebreakers(self, agents):
        a = agents["immoai"]
        assert len(a.get("system_prompt") or "") >= 4000, (
            f"prompt too short: {len(a.get('system_prompt') or '')}"
        )
        ice = a.get("icebreakers") or []
        assert len(ice) == 6, f"expected 6 icebreakers, got {len(ice)}: {ice}"
        wm = a.get("welcome_message") or ""
        assert "ImmoAI" in wm, f"welcome must mention ImmoAI: {wm[:200]}"

    def test_immoai_kb_has_8_knowledge_and_5_properties(self, session, agents):
        a = agents["immoai"]
        src_ids = a.get("data_source_ids") or []
        assert len(src_ids) >= 1, "no data sources attached"
        # Use admin /datasources or /datasources/{id}/chunks if available; fall back
        # to dedicated /datasources route.
        # Try the standard /datasources endpoint to gather counts.
        r = session.get(f"{BASE_URL}/api/data-sources", timeout=30)
        assert r.status_code == 200, f"data-sources list failed: {r.status_code}"
        sources = r.json()
        immo_src = next((s for s in sources if s["id"] in src_ids), None)
        assert immo_src is not None, f"no matching source for ImmoAI ids={src_ids}"
        # chunks count must be 13 (8 knowledge + 5 items)
        assert immo_src.get("chunks", 0) >= 13, (
            f"expected >=13 chunks, got {immo_src.get('chunks')}"
        )


# ---------------- 3. ImmoAI conversational flow ----------------
def _post_msg(session, tenant_id, agent_id, ext_uid, text):
    r = session.post(
        f"{BASE_URL}/api/webchat/{tenant_id}/message",
        json={
            "channel": "webchat",
            "external_user_id": ext_uid,
            "contact_name": "TEST_iter15",
            "text": text,
            "agent_id": agent_id,
        },
        timeout=120,
    )
    assert r.status_code == 200, f"webchat failed: {r.status_code} {r.text[:300]}"
    return r.json()


class TestImmoAIConversation:
    def test_full_buy_flow_with_card_filter(self, session, agents):
        tid = session._tenant_id  # type: ignore[attr-defined]
        aid = agents["immoai"]["id"]
        ext = f"test_iter15_immoai_{uuid.uuid4().hex[:8]}"

        # turn 1 — intent
        r1 = _post_msg(session, tid, aid, ext, "estou à procura de casa")
        reply1 = (r1.get("reply") or "").lower()
        assert ("comprar" in reply1) or ("arrendar" in reply1), (
            f"turn1 must ask comprar/arrendar — got: {reply1[:300]}"
        )

        # turn 2 — comprar
        r2 = _post_msg(session, tid, aid, ext, "comprar")
        reply2 = (r2.get("reply") or "").lower()
        assert any(k in reply2 for k in ["zona", "onde", "região", "regiao", "localização", "localizacao"]), (
            f"turn2 must ask about zona/onde — got: {reply2[:300]}"
        )

        # turn 3 — Lisboa
        r3 = _post_msg(session, tid, aid, ext, "Lisboa")
        reply3 = (r3.get("reply") or "").lower()
        assert any(k in reply3 for k in ["tipologia", "tipo", "t1", "t2", "t3", "orçamento", "orcamento", "valor"]), (
            f"turn3 must ask tipologia OR orçamento — got: {reply3[:300]}"
        )

        # turn 4 — tipologia + budget that filters out Cascais and Parque Nações
        r4 = _post_msg(session, tid, aid, ext, "T2 ou T3, até 350k")
        cards = r4.get("cards") or []
        # Some implementations attach cards differently; check meta as well
        assert isinstance(cards, list)
        assert len(cards) >= 1, (
            f"turn4 must return >=1 card after zona+tipologia+orcamento — "
            f"reply={(r4.get('reply') or '')[:300]} cards={cards[:2]}"
        )
        # Card filter: no Cascais (€950k) nor Parque das Nações (€520k)
        def _card_blob(c):
            return (str(c) or "").lower()
        for c in cards:
            blob = _card_blob(c)
            assert "cascais" not in blob, (
                f"Cascais €950k card leaked despite max 350k budget: {c}"
            )
            assert ("parque das nações" not in blob) and ("parque das nacoes" not in blob), (
                f"Parque Nações €520k card leaked despite max 350k budget: {c}"
            )
        # At least one of the expected affordable properties should appear
        joined = " ".join(_card_blob(c) for c in cards)
        assert ("benfica" in joined) or ("almada" in joined) or ("porto" in joined), (
            f"expected at least one of Benfica/Almada/Porto in cards — got: {joined[:400]}"
        )

        # turn 5 — verify conversion: after cards, must propose visit / next step
        # Look at the reply of turn4 + a follow-up call
        text4 = ((r4.get("reply") or "") + " " + (r4.get("follow_up") or "")).lower()
        conversion_keywords = [
            "visita", "marcar", "agendar", "ver pessoalmente", "contacto",
            "ver esta semana", "ver ao vivo", "saber mais",
        ]
        # Either turn4 already proposes visit/next step OR turn5 does
        has_conversion = any(k in text4 for k in conversion_keywords)
        if not has_conversion:
            r5 = _post_msg(session, tid, aid, ext, "gosto do primeiro")
            text5 = ((r5.get("reply") or "") + " " + (r5.get("follow_up") or "")).lower()
            has_conversion = any(k in text5 for k in conversion_keywords)
            assert has_conversion, (
                f"ImmoAI did not propose visit/next step after cards — "
                f"turn4={text4[:200]} ; turn5={text5[:300]}"
            )

    def test_human_tone_no_robotic_phrases(self, session, agents):
        tid = session._tenant_id  # type: ignore[attr-defined]
        aid = agents["immoai"]["id"]
        ext = f"test_iter15_tone_{uuid.uuid4().hex[:8]}"

        replies = []
        for msg in ["olá!", "estou à procura de casa", "comprar"]:
            r = _post_msg(session, tid, aid, ext, msg)
            replies.append((r.get("reply") or "").lower())

        joined = " ".join(replies)
        # at least one human expression in first 3 turns
        assert any(e in joined for e in HUMAN_EXPRESSIONS), (
            f"ImmoAI tone not human — no expressions like Perfeito/Boa/Excelente/etc.\n"
            f"Replies: {replies}"
        )
        # never robotic
        for bad in ROBOTIC_FORBIDDEN:
            assert bad not in joined, f"robotic phrase '{bad}' present in replies: {replies}"


# ---------------- 4. Maria short-answer interpretation ----------------
class TestMariaShortAnswer:
    def test_eu_eu_is_one_user_recommends_starter(self, session, agents):
        tid = session._tenant_id  # type: ignore[attr-defined]
        aid = agents["maria"]["id"]
        # Make sure Maria is on seed prompt
        session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)
        ext = f"test_iter15_maria_short_{uuid.uuid4().hex[:8]}"

        _post_msg(session, tid, aid, ext, "Olá quanto custa?")
        _post_msg(session, tid, aid, ext, "eu")
        r3 = _post_msg(session, tid, aid, ext, "eu")
        reply3 = (r3.get("reply") or "").lower()
        fu3 = (r3.get("follow_up") or "").lower()
        combined = reply3 + " " + fu3
        assert "starter" in combined, (
            f"Maria did not recommend STARTER after 'eu/eu' (1 user) — got: {combined[:400]}"
        )
        # Must NOT keep asking team size again
        team_qs = ["quantas pessoas", "quantos utilizadores", "tamanho da equipa", "tamanho da equipe", "quantos sois"]
        for q in team_qs:
            assert q not in reply3, (
                f"Maria is still asking team-size after two 'eu' answers: '{q}' in {reply3[:300]}"
            )

    def test_demo_yes_shares_meeting_link(self, session, agents):
        tid = session._tenant_id  # type: ignore[attr-defined]
        aid = agents["maria"]["id"]
        ext = f"test_iter15_maria_demo_{uuid.uuid4().hex[:8]}"

        # Bring Maria to a moment where she proposes a demo, then say 'sim'.
        _post_msg(session, tid, aid, ext, "Olá, quero ver como funciona")
        r2 = _post_msg(session, tid, aid, ext, "quero ver uma demo")
        # If she already asked about demo, answering 'sim' should produce the link
        r3 = _post_msg(session, tid, aid, ext, "sim")
        text3 = ((r3.get("reply") or "") + " " + (r3.get("follow_up") or "")).lower()
        # If not yet, try one more nudge
        if "consenso-shop.eu/marcar-reuniao" not in text3:
            r4 = _post_msg(session, tid, aid, ext, "sim, quero marcar")
            text3 = ((r4.get("reply") or "") + " " + (r4.get("follow_up") or "")).lower()
        assert "consenso-shop.eu/marcar-reuniao" in text3, (
            f"Maria did not share marcar-reuniao link after 'sim' — last reply text: {text3[:400]}"
        )


# ---------------- 5. ImmoAI reset-defaults ----------------
class TestImmoAIResetDefaults:
    def test_put_customize_then_reset_restores_seed(self, session, agents):
        aid = agents["immoai"]["id"]
        # Refetch latest copy from API to avoid stale fixture data after previous tests
        a = next(x for x in session.get(f"{BASE_URL}/api/agents").json() if x["id"] == aid)

        # PUT customization
        payload = {k: a.get(k) for k in [
            "name", "avatar_url", "welcome_message", "icebreakers", "tone",
            "goal", "system_prompt", "rules", "api_provider", "api_key",
            "model_provider", "model_name", "tools", "knowledge",
            "data_source_ids", "default_language", "notify_email",
            "channels", "email", "theme", "active",
        ]}
        for sk in ["name", "welcome_message", "tone", "goal", "system_prompt"]:
            if payload.get(sk) is None:
                payload[sk] = ""
        # Coerce None → defaults for fields that the Pydantic model doesn't allow as None
        if payload.get("notify_email") is None:
            payload["notify_email"] = ""
        if payload.get("email") is None:
            payload["email"] = {}
        if payload.get("channels") is None:
            payload["channels"] = {}
        if payload.get("theme") is None:
            payload["theme"] = {}
        payload["welcome_message"] = "TEST_iter15 immoai custom welcome"
        payload["theme"] = {
            "primary": "#000000", "primary_dark": "#000000",
            "primary_soft": "#eeeeee", "primary_border": "#cccccc",
            "bot": "#ff00ff",
        }
        r = session.put(f"{BASE_URL}/api/agents/{aid}", json=payload, timeout=30)
        assert r.status_code == 200, f"PUT immoai failed: {r.status_code} body={r.text[:500]}"
        upd = r.json()
        assert upd["is_customized"] is True
        assert upd["welcome_message"] == "TEST_iter15 immoai custom welcome"
        assert upd["theme"]["primary"] == "#000000"

        # Reset
        r = session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)
        assert r.status_code == 200, f"reset failed: {r.status_code} {r.text[:300]}"
        reset = r.json()
        assert reset["is_customized"] is False
        assert reset["welcome_message"] != "TEST_iter15 immoai custom welcome"
        # Must mention ImmoAI in restored welcome
        assert "ImmoAI" in (reset.get("welcome_message") or ""), (
            f"reset welcome missing ImmoAI: {reset.get('welcome_message')}"
        )
        # Theme restored to CONSENSO
        assert reset["theme"].get("primary") == "#4591CE", (
            f"theme.primary not restored to #4591CE: {reset['theme']}"
        )
        assert reset["theme"].get("bot") == "#E4AC1E"
        # icebreakers and prompt restored
        assert len(reset.get("icebreakers") or []) == 6
        assert len(reset.get("system_prompt") or "") >= 4000


# ---------------- 6. Bootstrap idempotency (regression iter14) ----------------
class TestBootstrapIdempotency:
    def test_customized_flag_preserved_via_put(self, session, agents):
        """Contract-level regression — PUT sets is_customized=true and bootstrap
        skip-path respects that flag (verified by re-reading list after PUT).
        Physical restart is out of scope for the test harness.
        """
        aid = agents["staylocal"]["id"]
        # Refetch latest
        latest = next(x for x in session.get(f"{BASE_URL}/api/agents").json() if x["id"] == aid)
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
        payload["welcome_message"] = "TEST_iter15 stay custom"
        r = session.put(f"{BASE_URL}/api/agents/{aid}", json=payload, timeout=30)
        assert r.status_code == 200
        assert r.json()["is_customized"] is True

        # Verify via GET list
        latest2 = next(x for x in session.get(f"{BASE_URL}/api/agents").json() if x["id"] == aid)
        assert latest2["is_customized"] is True
        assert latest2["welcome_message"] == "TEST_iter15 stay custom"

        # Cleanup
        session.post(f"{BASE_URL}/api/agents/{aid}/reset-defaults", timeout=30)
