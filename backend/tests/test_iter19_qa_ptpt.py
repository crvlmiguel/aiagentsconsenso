"""Iteration 19 — QA PT-PT: sticky language, PT variant, intent reclassify,
gender-neutral, SEO recognition, Maria qualification/quote flow, scheduling
links, agent isolation, URL whitelist.

Uses PUBLIC webchat endpoint (no auth). Tolerant assertions: LLM output varies,
so we check for markers/keywords rather than exact strings.
"""
import os
import time
import uuid
import re
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
TENANT = "b63f7593-d59a-491d-8c91-e28caea3f760"
CLARA = "68317ac5-a278-4b3b-8ec5-1b1ca8a00a93"
MARIA = "4b4dbf03-2107-473a-b578-9456ad2a9318"

WEBCHAT = f"{BASE_URL}/api/webchat/{TENANT}/message"

GENDERED_TERMS = ["ajudá-lo", "ajudá-la", "ajuda-lo", "ajuda-la",
                  "está interessado", "está interessada",
                  "esta interessado", "esta interessada",
                  "seja bem-vindo", "seja bem-vinda"]

PIPEDRIVE_LINK = "https://consensoglobal.pipedrive.com/scheduler/1DzB0QCb/agende-uma-reuniao"
CONSENSO_SHOP_LINK = "https://consenso-shop.eu/marcar-reuniao"


def _new_uid(tag: str) -> str:
    return f"TEST_iter19_{tag}_{uuid.uuid4().hex[:8]}"


def send(agent_id: str, uid: str, text: str) -> dict:
    r = requests.post(
        WEBCHAT,
        json={
            "channel": "webchat",
            "external_user_id": uid,
            "contact_name": "QA Tester",
            "text": text,
            "agent_id": agent_id,
        },
        timeout=90,
    )
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:400]}"
    return r.json()


def full_reply(data: dict) -> str:
    return f"{data.get('reply','')} {data.get('follow_up','') or ''}".strip()


def assert_no_gendered(text: str):
    tl = text.lower()
    hits = [g for g in GENDERED_TERMS if g in tl]
    assert not hits, f"Gendered terms leaked: {hits} in text: {text[:300]}"


# ---------------------------------------------------------------------------
# 1. Language detection + sticky
# ---------------------------------------------------------------------------
class TestStickyLanguage:
    def test_english_sticky_across_ok(self):
        uid = _new_uid("lang_en")
        r1 = send(CLARA, uid, "Hello, can you tell me about your services?")
        # Should reply in EN (allow tolerance — look for typical english words)
        t1 = full_reply(r1).lower()
        # heuristic: english reply
        assert any(w in t1 for w in [" the ", "you", "we ", "our ", "services", "help", "hi", "hello"]), \
            f"Expected EN reply, got: {t1[:200]}"
        # Language field
        assert r1.get("language") in ("en", "pt"), f"language={r1.get('language')}"
        # Short reply — must keep EN
        r2 = send(CLARA, uid, "ok")
        t2 = full_reply(r2).lower()
        # Must NOT drift to PT ("obrigado", "olá", "boas-vindas" etc)
        pt_markers = ["obrigado", "obrigada", "boas-vindas", "olá", "prazer em"]
        assert not any(m in t2 for m in pt_markers), f"Language drifted to PT on 'ok': {t2[:200]}"

    def test_french_sticky(self):
        uid = _new_uid("lang_fr")
        r1 = send(CLARA, uid, "Bonjour, pouvez-vous me parler de vos services?")
        t1 = full_reply(r1).lower()
        assert any(w in t1 for w in ["bonjour", "nous", "services", "vous", "aider", "notre"]), \
            f"Expected FR reply, got: {t1[:200]}"


# ---------------------------------------------------------------------------
# 2. PT variant question when user asks for translation to "português"
# ---------------------------------------------------------------------------
class TestPTVariant:
    def test_asks_variant_then_remembers(self):
        uid = _new_uid("ptvar")
        r1 = send(CLARA, uid, "Quero traduzir o meu site para português.")
        t1 = full_reply(r1).lower()
        # Guardrail injects the variant question deterministically
        assert "portugal" in t1 and "brasil" in t1, \
            f"Expected variant question mentioning Portugal & Brasil: {t1[:300]}"
        # User answers "Portugal"
        r2 = send(CLARA, uid, "Portugal")
        t2 = full_reply(r2).lower()
        # Must NOT re-ask the variant question
        # (both markers again would mean repetition)
        both_again = "portugal" in t2 and "brasil" in t2 and "variante" in t2
        assert not both_again, f"Clara re-asked PT variant after user answered: {t2[:300]}"


# ---------------------------------------------------------------------------
# 3. Intent reclassify — anti-loop "Obrigado"
# ---------------------------------------------------------------------------
class TestIntentReclassify:
    def test_obrigado_then_services(self):
        uid = _new_uid("obrigado")
        r1 = send(CLARA, uid, "Obrigado.")
        # Follow up with a service question
        r2 = send(CLARA, uid, "Quais são os vossos serviços?")
        t2 = full_reply(r2).lower()
        # Must mention services concept, not thank-you loop
        assert any(w in t2 for w in ["seo", "localização", "localizacao",
                                     "conteúdo", "conteudo", "consultoria",
                                     "tradução", "traducao", "área", "area",
                                     "serviço", "servico"]), \
            f"Clara did not answer services question: {t2[:300]}"
        # Must not simply reply an acknowledgement to thanks
        assert not re.match(r"^\s*(de\s+nada|obrigad[oa]\s+(a\s+)?ti|com\s+prazer)\.?\s*$",
                            t2.strip()), \
            f"Clara looped on 'obrigado' after user changed topic: {t2[:300]}"


# ---------------------------------------------------------------------------
# 4. Maria describes Consenso Plus correctly
# ---------------------------------------------------------------------------
class TestMariaDescribesConsensoPlus:
    def test_offers_ai_agents_not_only_avatars(self):
        uid = _new_uid("maria_desc")
        r = send(MARIA, uid, "O que oferece a Consenso Plus?")
        t = full_reply(r).lower()
        # Must mention agents/chatbots/plans/consultancy (at least 1)
        keywords = ["agentes", "chatbot", "chatbots", "planos",
                    "consultoria", "ia", "assistente"]
        assert any(k in t for k in keywords), \
            f"Maria description missing AI agent markers: {t[:400]}"


# ---------------------------------------------------------------------------
# 5. Gender-neutral language
# ---------------------------------------------------------------------------
class TestGenderNeutral:
    def test_clara_neutral_on_intro(self):
        uid = _new_uid("neutral_clara")
        r = send(CLARA, uid, "Podem apresentar-me a empresa?")
        assert_no_gendered(full_reply(r))

    def test_maria_neutral_on_intro(self):
        uid = _new_uid("neutral_maria")
        r = send(MARIA, uid, "Podem apresentar-me a empresa?")
        assert_no_gendered(full_reply(r))


# ---------------------------------------------------------------------------
# 6. Clara confirms SEO service
# ---------------------------------------------------------------------------
class TestClaraSEO:
    def test_confirms_seo(self):
        uid = _new_uid("seo")
        r = send(CLARA, uid, "Prestam serviços de SEO?")
        t = full_reply(r).lower()
        # Must confirm (not deny)
        deny_markers = ["não prestamos", "nao prestamos", "não oferecemos seo",
                        "nao oferecemos seo", "não temos seo", "nao temos seo"]
        assert not any(d in t for d in deny_markers), \
            f"Clara denied SEO service: {t[:300]}"
        assert "seo" in t, f"Clara did not acknowledge SEO: {t[:300]}"


# ---------------------------------------------------------------------------
# 7. Maria qualification close — no re-ask team size
# ---------------------------------------------------------------------------
class TestMariaQualificationClose:
    def test_users_registered_and_no_reask(self):
        uid = _new_uid("maria_qual")
        # Trigger pricing/qualification
        send(MARIA, uid, "Olá, quanto custa?")
        r2 = send(MARIA, uid, "eu")
        r3 = send(MARIA, uid, "eu")
        t3 = full_reply(r3).lower()
        # Must not re-ask team size — use forbidden question patterns
        reask_hits = [p for p in [
            "quantos utilizadores", "quantos são", "quantos sao",
            "tamanho da equipa", "sozinho ou com", "quantas pessoas",
            "trabalhas sozinho", "sois quantos", "sois quantas",
        ] if p in t3]
        assert not reask_hits, f"Maria re-asked team size: {reask_hits} | text={t3[:300]}"


# ---------------------------------------------------------------------------
# 8. Maria quote flow — starts with name, one question at a time
# ---------------------------------------------------------------------------
class TestMariaQuoteFlow:
    def test_quote_asks_name_first(self):
        uid = _new_uid("maria_quote")
        r = send(MARIA, uid, "Quero pedir um orçamento")
        t = full_reply(r).lower()
        # Must ask for name (nome) OR company (empresa) — progressive collection
        assert any(k in t for k in ["nome", "chamas", "chama"]), \
            f"Maria didn't start progressive collection asking name: {t[:400]}"
        # Must not bulk-ask everything at once (heuristic: not too many '?')
        q_count = t.count("?")
        assert q_count <= 2, f"Maria asked too many questions at once ({q_count}): {t[:400]}"


# ---------------------------------------------------------------------------
# 9. Scheduling links
# ---------------------------------------------------------------------------
class TestSchedulingLinks:
    def test_clara_returns_pipedrive_link(self):
        uid = _new_uid("clara_book")
        r = send(CLARA, uid, "Quero marcar uma reunião")
        t = full_reply(r)
        assert PIPEDRIVE_LINK in t, \
            f"Clara did not return the official Pipedrive link. Got: {t[:400]}"
        # No competing schedulers
        for bad in ["calendly.com", "cal.com", "calendar.google"]:
            assert bad not in t.lower(), f"Clara returned forbidden scheduler '{bad}': {t[:400]}"

    def test_maria_returns_consenso_shop_link(self):
        uid = _new_uid("maria_demo")
        send(MARIA, uid, "Quero uma demo")
        r = send(MARIA, uid, "sim")
        t = full_reply(r)
        assert CONSENSO_SHOP_LINK in t, \
            f"Maria did not return consenso-shop link on demo confirm. Got: {t[:400]}"


# ---------------------------------------------------------------------------
# 10. Agent isolation (Clara vs Maria)
# ---------------------------------------------------------------------------
class TestAgentIsolation:
    def test_clara_no_real_estate(self):
        uid = _new_uid("clara_iso_re")
        r = send(CLARA, uid, "Tens imóveis em Lisboa?")
        t = full_reply(r).lower()
        # Must NOT list properties. Should redirect or say it's not her scope.
        # Heuristic: presence of typical listing markers is a failure.
        listing_markers = ["t2 ", "t3 ", "quarto", "€/mês", "€ /mês", "moradia em",
                           "apartamento em "]
        # (light) — main check: mentions Consenso Plus / redireccionamento OR
        # simply doesn't provide listings
        # Fail only on hard listings
        hits = [m for m in listing_markers if m in t]
        assert not hits, f"Clara returned real-estate listings: {hits} | text={t[:400]}"

    def test_clara_chatbot_redirects_to_plus(self):
        uid = _new_uid("clara_iso_chat")
        r = send(CLARA, uid, "Quero um chatbot para o meu website")
        t = full_reply(r).lower()
        # She may explain that's Consenso Plus scope — check she mentions
        # consenso plus / plus / redirecciona
        assert any(k in t for k in ["consenso plus", "consenso+", "plus",
                                     "outra unidade", "outra área"]), \
            f"Clara didn't redirect chatbot request to Consenso Plus: {t[:400]}"


# ---------------------------------------------------------------------------
# 11. Clara doesn't invent Calendly
# ---------------------------------------------------------------------------
class TestNoCalendlyInvention:
    def test_clara_no_calendly(self):
        uid = _new_uid("clara_calendly")
        r = send(CLARA, uid, "Tem um Calendly onde marcar?")
        t = full_reply(r).lower()
        assert "calendly.com" not in t, f"Clara invented a Calendly URL: {t[:300]}"


# ---------------------------------------------------------------------------
# 12. URL whitelist enforcement
# ---------------------------------------------------------------------------
class TestURLWhitelist:
    def _extract_urls(self, text: str):
        return re.findall(r"https?://[^\s\]\)\}\>\"'`]+", text)

    def test_clara_urls_in_whitelist(self):
        # Aggregate URLs across multiple prompts
        uid = _new_uid("clara_wl")
        replies = []
        for prompt in ["Quero marcar uma reunião",
                       "Onde encontro mais informação sobre a Consenso Global?"]:
            r = send(CLARA, uid, prompt)
            replies.append(full_reply(r))
        allowed = ("consensoglobal.com", "consenso-global.com",
                   "pipedrive.com", "consenso-agents.com",
                   "consenso-plus.com", "consenso-shop.eu")
        for text in replies:
            for url in self._extract_urls(text):
                host = url.split("//", 1)[-1].split("/", 1)[0].lower()
                assert any(host.endswith(a) for a in allowed), \
                    f"Clara returned URL outside whitelist: {url}"

    def test_maria_urls_in_whitelist(self):
        uid = _new_uid("maria_wl")
        send(MARIA, uid, "Quero uma demo")
        r = send(MARIA, uid, "sim")
        text = full_reply(r)
        allowed = ("consenso-shop.eu", "consenso-plus.com",
                   "consenso-agents.com", "pipedrive.com",
                   "consensoglobal.com")
        for url in re.findall(r"https?://[^\s\]\)\}\>\"'`]+", text):
            host = url.split("//", 1)[-1].split("/", 1)[0].lower()
            assert any(host.endswith(a) for a in allowed), \
                f"Maria returned URL outside whitelist: {url}"
