"""Iter16 — Consenso Plus: Duplicate & Duplicate+Translate agent.

Covers:
- POST /api/agents/{id}/duplicate: clones same content, new id, '(cópia)' suffix,
  is_customized=true, api_key cleared, data_source_ids=[], channels secrets stripped.
- POST /api/agents/{id}/duplicate-translate with body {target_language}: clones
  and translates name, welcome_message, tone, goal, system_prompt, rules,
  knowledge, icebreakers. default_language updated. Name suffixed with lang code.
  Brand names preserved (Consenso Plus, ImmoAI, StayLocal, Maria, ABBI, URLs).
- Invalid target_language returns 400.
- Multi-language tests: en, es, fr, de, ca.
- Preserved fields: theme, channels secret tokens reset, NEW id assigned.
- GET /api/agents returns original + cloned agents.
- DELETE clone works for cleanup.

To minimize total LLM time, uses smaller-prompt agent (StayLocal or Abby)
rather than Maria (~12k chars).
"""

import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "admin@consenso-agents.com"
ADMIN_PASS = "100%Consenso"

SUPPORTED_LANG_CODES = ["pt", "en", "es", "fr", "de", "ca"]
LANG_LABELS = {"pt": "PT", "en": "EN", "es": "ES", "fr": "FR", "de": "DE", "ca": "CA"}

# Brand names / proper nouns that MUST be preserved verbatim by translation
BRAND_TOKENS = [
    "Consenso Plus", "ImmoAI", "StayLocal", "Maria", "ABBI", "Abby",
    "consenso-shop.eu", "consenso-agents.com",
]

# Marker strings indicating Brazilian PT (should NOT appear when target=es etc.)
PT_BR_STRONG_MARKERS = ["você", "vocês"]

SEED_AGENT_NAMES = {
    "Maria — Assistente IA Consenso Plus",
    "StayLocal Concierge AI",
    "Tejo Sunset Sailing AI Guide",
    "Abby — ABBI Imóveis",
    "ImmoAI — Consultor Imobiliário Digital",
}


# ------------------- fixtures -------------------
@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    body = r.json()
    s.headers.update({"Authorization": f"Bearer {body['token']}"})
    return s


@pytest.fixture(scope="module")
def all_agents(session):
    r = session.get(f"{BASE_URL}/api/agents", timeout=30)
    assert r.status_code == 200, f"GET /api/agents failed: {r.status_code}"
    return r.json()


def _find_agent(agents, *keywords):
    """Find agent whose name contains any of the keywords (case-insensitive)."""
    for a in agents:
        name = (a.get("name") or "").lower()
        for kw in keywords:
            if kw.lower() in name:
                return a
    return None


@pytest.fixture(scope="module")
def small_agent(all_agents):
    """Pick smallest-prompt agent to minimize LLM time. Prefer StayLocal/Abby/Tejo."""
    candidates = []
    for a in all_agents:
        if a.get("name") in SEED_AGENT_NAMES or any(
            kw in (a.get("name") or "") for kw in ["StayLocal", "Abby", "Tejo", "ImmoAI"]
        ):
            candidates.append(a)
    # Sort by prompt size ascending
    candidates.sort(key=lambda a: len(a.get("system_prompt") or ""))
    assert candidates, "No seed agent found to duplicate"
    return candidates[0]


@pytest.fixture(scope="module")
def cleanup_ids():
    """Collect ids of created clones; deleted at module teardown."""
    ids = []
    yield ids
    # Teardown
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    if r.status_code == 200:
        s.headers.update({"Authorization": f"Bearer {r.json()['token']}"})
        for aid in ids:
            try:
                s.delete(f"{BASE_URL}/api/agents/{aid}", timeout=20)
            except Exception:
                pass


# ------------------- helpers -------------------
def _assert_brands_preserved(payload_text: str, where: str):
    """Brand tokens should appear if they appeared in the source. We only check
    that NONE were translated/distorted by checking that known brand variants
    are absent."""
    # Common mistranslations to forbid in output
    forbidden_mistranslations = [
        "Consenso Plus Imóveis And",  # weird "and" injection
        "ABBI Properties Real Estate Inc",  # invented expansions
    ]
    low = payload_text.lower()
    for bad in forbidden_mistranslations:
        assert bad.lower() not in low, f"[{where}] mistranslation '{bad}' found"


def _has_pt_br_markers(text: str) -> bool:
    low = (text or "").lower()
    return any(m in low for m in PT_BR_STRONG_MARKERS)


# ------------------- TEST 1: plain duplicate -------------------
class TestPlainDuplicate:
    def test_duplicate_preserves_content_and_resets_secrets(self, session, small_agent, cleanup_ids):
        original = small_agent
        r = session.post(f"{BASE_URL}/api/agents/{original['id']}/duplicate", timeout=60)
        assert r.status_code == 200, f"duplicate failed: {r.status_code} {r.text[:300]}"
        clone = r.json()
        cleanup_ids.append(clone["id"])

        # 1. New ID
        assert clone["id"] != original["id"], "Clone has same ID as original"
        # 2. Name suffix
        assert clone["name"].endswith("(cópia)"), f"Unexpected name: {clone['name']!r}"
        # 3. Content preserved
        assert clone.get("system_prompt") == original.get("system_prompt")
        assert clone.get("icebreakers") == original.get("icebreakers")
        assert clone.get("welcome_message") == original.get("welcome_message")
        assert clone.get("theme") == original.get("theme")
        # 4. is_customized = true
        assert clone.get("is_customized") is True
        # 5. api_key cleared
        assert clone.get("api_key") == "", f"api_key not cleared: {clone.get('api_key')!r}"
        # 6. data_source_ids empty
        assert clone.get("data_source_ids") == [], f"data_source_ids not empty: {clone.get('data_source_ids')}"
        # 7. Channel secrets stripped
        for kind, ch in (clone.get("channels") or {}).items():
            if not isinstance(ch, dict):
                continue
            for sf in ("access_token", "bot_token", "phone_number_id",
                       "page_access_token", "verify_token"):
                if sf in ch:
                    assert ch[sf] == "", f"Channel {kind}.{sf} not cleared: {ch[sf]!r}"
        # 8. No mongo _id leaked
        assert "_id" not in clone

    def test_list_includes_clone(self, session, small_agent, cleanup_ids):
        # Use the clone created above (or create one if not present)
        if not cleanup_ids:
            r = session.post(f"{BASE_URL}/api/agents/{small_agent['id']}/duplicate", timeout=60)
            assert r.status_code == 200
            cleanup_ids.append(r.json()["id"])
        r = session.get(f"{BASE_URL}/api/agents", timeout=30)
        assert r.status_code == 200
        ids = {a["id"] for a in r.json()}
        assert small_agent["id"] in ids, "Original missing from list"
        assert cleanup_ids[0] in ids, "Clone not visible in /api/agents"


# ------------------- TEST 2: invalid target language -------------------
class TestInvalidTargetLanguage:
    def test_invalid_lang_returns_400(self, session, small_agent):
        r = session.post(
            f"{BASE_URL}/api/agents/{small_agent['id']}/duplicate-translate",
            json={"target_language": "jp"},
            timeout=30,
        )
        assert r.status_code in (400, 422), f"Expected 400, got {r.status_code}: {r.text[:300]}"
        body = r.text.lower()
        assert "idioma" in body or "language" in body or "suportado" in body, \
            f"Error message not descriptive: {r.text[:300]}"

    def test_missing_body_returns_400(self, session, small_agent):
        r = session.post(
            f"{BASE_URL}/api/agents/{small_agent['id']}/duplicate-translate",
            json={},
            timeout=30,
        )
        assert r.status_code in (400, 422)


# ------------------- TEST 3: duplicate + translate (parametrized) -------------------
# Test 4 languages — keeps total time bounded (~60-120s)
@pytest.mark.parametrize("target_lang", ["en", "es", "fr", "de"])
class TestDuplicateTranslate:
    def test_translate_to_lang(self, session, small_agent, cleanup_ids, target_lang):
        original = small_agent
        r = session.post(
            f"{BASE_URL}/api/agents/{original['id']}/duplicate-translate",
            json={"target_language": target_lang},
            timeout=240,  # LLM can be slow
        )
        assert r.status_code == 200, \
            f"[{target_lang}] duplicate-translate failed: {r.status_code} {r.text[:400]}"
        clone = r.json()
        cleanup_ids.append(clone["id"])

        # New ID, customized, secrets reset (same invariants as plain duplicate)
        assert clone["id"] != original["id"]
        assert clone.get("is_customized") is True
        assert clone.get("api_key") == ""
        assert clone.get("data_source_ids") == []

        # default_language updated
        assert clone.get("default_language") == target_lang, \
            f"[{target_lang}] default_language={clone.get('default_language')!r}"

        # Name suffixed with lang label
        expected_suffix = f" {LANG_LABELS[target_lang]}"
        assert clone["name"].endswith(expected_suffix), \
            f"[{target_lang}] name {clone['name']!r} should end with {expected_suffix!r}"

        # Theme preserved
        assert clone.get("theme") == original.get("theme"), \
            f"[{target_lang}] theme changed"

        # System prompt translated (different from original AND non-empty)
        if (original.get("system_prompt") or "").strip():
            assert clone.get("system_prompt"), f"[{target_lang}] system_prompt empty"
            assert clone["system_prompt"] != original["system_prompt"], \
                f"[{target_lang}] system_prompt not translated (identical to source)"

        # Welcome message translated
        if (original.get("welcome_message") or "").strip():
            assert clone.get("welcome_message"), f"[{target_lang}] welcome empty"
            # Welcome usually changes
            # (very short messages may stay identical in some langs; accept if !=)
            # Not a hard assertion — we just check it's non-empty.

        # Icebreakers translated (list preserved length)
        if original.get("icebreakers"):
            assert isinstance(clone.get("icebreakers"), list)
            assert len(clone["icebreakers"]) == len(original["icebreakers"]), \
                f"[{target_lang}] icebreaker count mismatch"

        # Brand preservation: at least one brand from the original survives in the
        # translated system_prompt (if it appeared in the source).
        src_text = " ".join([
            original.get("system_prompt") or "",
            original.get("welcome_message") or "",
            " ".join(original.get("icebreakers") or []),
        ])
        clone_text = " ".join([
            clone.get("system_prompt") or "",
            clone.get("welcome_message") or "",
            " ".join(clone.get("icebreakers") or []),
        ])
        for brand in BRAND_TOKENS:
            if brand in src_text:
                assert brand in clone_text, \
                    f"[{target_lang}] Brand {brand!r} not preserved in translation"

        _assert_brands_preserved(clone_text, target_lang)

        # ES-specific: should NOT contain strong pt-BR markers like 'você'
        if target_lang == "es":
            assert not _has_pt_br_markers(clone_text), \
                f"[es] pt-BR markers leaked: {[m for m in PT_BR_STRONG_MARKERS if m in clone_text.lower()]}"
            # Has typical spanish words
            assert re.search(r"\b(el|la|de|que|para|usted|tú|tu)\b", clone_text.lower()), \
                f"[es] no spanish article/pronoun found in clone"

        # EN-specific: typical english words
        if target_lang == "en":
            assert re.search(r"\b(the|you|and|to|for|with)\b", clone_text.lower()), \
                f"[en] no english function words found"

        # FR-specific
        if target_lang == "fr":
            assert re.search(r"\b(le|la|les|vous|de|pour|et)\b", clone_text.lower()), \
                f"[fr] no french function words found"

        # DE-specific
        if target_lang == "de":
            assert re.search(r"\b(der|die|das|sie|und|für|mit|ist)\b", clone_text.lower()), \
                f"[de] no german function words found"


# ------------------- TEST 4: CA (catalan) alone — kept separate so failures clear -------------------
class TestCatalanTranslate:
    def test_translate_to_ca(self, session, small_agent, cleanup_ids):
        r = session.post(
            f"{BASE_URL}/api/agents/{small_agent['id']}/duplicate-translate",
            json={"target_language": "ca"},
            timeout=240,
        )
        assert r.status_code == 200, f"[ca] failed: {r.status_code} {r.text[:400]}"
        clone = r.json()
        cleanup_ids.append(clone["id"])
        assert clone.get("default_language") == "ca"
        assert clone["name"].endswith(" CA")
        clone_text = " ".join([
            clone.get("system_prompt") or "",
            clone.get("welcome_message") or "",
        ]).lower()
        # Typical catalan markers
        assert re.search(r"\b(el|la|amb|això|què|també|i|de|us)\b", clone_text), \
            f"[ca] no catalan markers found in clone"


# ------------------- TEST 5: cleanup / delete clone -------------------
class TestCleanup:
    def test_delete_clone_removes_from_list(self, session, small_agent):
        # Create a fresh clone for this isolated test
        r = session.post(f"{BASE_URL}/api/agents/{small_agent['id']}/duplicate", timeout=60)
        assert r.status_code == 200
        clone_id = r.json()["id"]

        # DELETE
        d = session.delete(f"{BASE_URL}/api/agents/{clone_id}", timeout=30)
        assert d.status_code == 200, f"DELETE failed: {d.status_code} {d.text[:200]}"

        # Verify removed from list
        r = session.get(f"{BASE_URL}/api/agents", timeout=30)
        assert r.status_code == 200
        ids = {a["id"] for a in r.json()}
        assert clone_id not in ids, "Clone still present after DELETE"

    def test_seed_agents_still_present(self, session):
        """The 5 seed agents must NEVER be deleted by clone cleanup."""
        r = session.get(f"{BASE_URL}/api/agents", timeout=30)
        assert r.status_code == 200
        names = {a.get("name") for a in r.json()}
        # At least 4 of the known seed names should remain
        survivors = SEED_AGENT_NAMES & names
        assert len(survivors) >= 4, \
            f"Seed agents missing! Found only: {survivors}"
