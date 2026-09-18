"""Memória contextual da conversa — extrai factos já partilhados pelo
utilizador para que a IA nunca repita perguntas.

Determinístico (sem LLM). Corre a cada turno e produz um resumo
'JÁ SABEMOS:' que é injetado no system prompt.
"""
import re
from typing import List, Dict, Optional


_NUM_WORDS_PT = {
    "um": 1, "uma": 1, "uno": 1, "1": 1, "eu": 1, "só eu": 1, "apenas eu": 1, "sozinho": 1, "sozinha": 1,
    "dois": 2, "duas": 2, "2": 2,
    "três": 3, "tres": 3, "3": 3,
    "quatro": 4, "4": 4,
    "cinco": 5, "5": 5,
    "seis": 6, "6": 6,
    "sete": 7, "7": 7,
    "oito": 8, "8": 8,
    "nove": 9, "9": 9,
    "dez": 10, "10": 10,
    "vinte": 20, "20": 20,
    "cinquenta": 50, "50": 50,
    "cem": 100, "100": 100,
}

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_RE = re.compile(r"\+?\d[\d\s.\-]{7,}\d")
_NAME_INTRO_RE = re.compile(
    r"(?:chamo[\- ]?me|sou\s+o|sou\s+a|me\s+chamo|o\s+meu\s+nome\s+[ée]|nome\s*[:\-]?\s*)\s*"
    r"([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+(?:\s+[A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+){0,3})",
    re.IGNORECASE,
)

_SECTOR_HINTS = [
    ("imobiliário",   ["imobiliária", "imovel", "imóvel", "imoveis", "imóveis", "casa para vender", "portefolio imobiliario", "agente imobiliario"]),
    ("hotelaria",     ["hotel", "pousada", "hostel", "resort"]),
    ("alojamento local", ["airbnb", "booking.com", "alojamento local", " al ", "anfitri"]),
    ("turismo",       ["turism", "tours", "experien"]),
    ("clínica",       ["clínica", "clinica", "dentista", "consult", "médico", "medico"]),
    ("restauração",   ["restaurante", "menu", "mesa"]),
    ("e-commerce",    ["e-commerce", "ecommerce", "loja online", "shopify", "encomenda"]),
    ("serviços B2B",  ["consultoria", "servi", "agência", "agencia"]),
]


def _extract_users_count(text: str) -> Optional[int]:
    """Detecta 'quantos utilizadores' — '1', 'um', 'só eu', 'apenas eu', 'sou apenas eu', 'eu' isolado."""
    t = text.lower().strip()

    # Padrões directos de '1 utilizador': "sou eu", "apenas eu", "só eu", "eu", "sozinho", "sozinha"
    if re.search(r"\b(?:s[óo]\s+)?(?:apenas\s+|s[óo]\s+|sou\s+)?eu\b(?!\s+(?:tenho|sou\s+\w{4,}))", t):
        return 1
    if re.search(r"\b(?:sozinh[oa]|so\s+um|apenas\s+(?:um|uma|eu))\b", t):
        return 1

    # 'N utilizador(es)', 'N pessoa(s)', 'N agente(s)', 'N na equipa'
    m = re.search(r"\b(\d{1,3})\s*(?:utilizador|usuario|pessoa|agente|colaborador|na\s+equipa|user)", t)
    if m:
        return int(m.group(1))

    # Palavra numérica + utilizador
    m = re.search(r"\b(um|uma|dois|duas|tr[êe]s|quatro|cinco|seis|sete|oito|nove|dez)\s+(?:utilizador|usuario|pessoa|agente|colaborador|user|na\s+equipa)", t)
    if m:
        return _NUM_WORDS_PT.get(m.group(1).lower())

    # Resposta isolada a pergunta de utilizadores (texto curto, só número/palavra)
    if len(t) <= 25:
        # "um", "1", "2 pessoas", "três"
        words = re.findall(r"\w+", t)
        if len(words) <= 4:
            for w in words:
                if w in _NUM_WORDS_PT:
                    return _NUM_WORDS_PT[w]
            m = re.match(r"^(\d{1,3})$", t)
            if m:
                return int(m.group(1))

    return None


def _extract_sector(text: str) -> Optional[str]:
    t = text.lower()
    for label, hints in _SECTOR_HINTS:
        if any(h in t for h in hints):
            return label
    return None


def _extract_name(text: str) -> Optional[str]:
    m = _NAME_INTRO_RE.search(text)
    if m:
        return m.group(1).strip()
    return None


def collect_facts(history: List[Dict], current_text: str = "") -> Dict[str, str]:
    """Percorre o histórico user→ai e extrai factos persistentes.
    Returns dict com chaves: users, sector, name, email, phone (todas opcionais)
    + flags de conversação: pricing_shown, demo_link_shared (evita repetição)."""
    facts: Dict[str, str] = {}
    user_texts: List[str] = []
    ai_texts: List[str] = []
    for m in history or []:
        if m.get("sender") == "user" and m.get("text"):
            user_texts.append(m["text"])
        elif m.get("sender") == "ai" and m.get("text"):
            ai_texts.append(m["text"])
    if current_text:
        user_texts.append(current_text)

    # === Conversational flags (anti-repetition) ===
    # Já apresentámos os planos? Se sim, NÃO voltar a listar.
    for t in ai_texts:
        tl = t.lower()
        if ("starter" in tl and "€49" in t) or ("📦 planos" in tl) or ("pro €74" in tl):
            facts["pricing_shown"] = "yes"
            break
    # Já partilhámos o link de agendamento?
    for t in ai_texts:
        if "consenso-shop.eu/marcar-reuniao" in t or "consensoglobal.pipedrive.com" in t:
            facts["demo_link_shared"] = "yes"
            break

    # === Confirmação de reunião/demo (sim → intent de agendar) ===
    _AFFIRMATIVE = {"sim", "s", "claro", "ok", "okay", "com certeza", "sim quero", "sim, quero", "quero", "vamos", "bora"}
    _MEETING_CTX = ("marcar", "reunião", "reuniao", "demo", "demonstra", "agendar", "agenda")
    last_ai = ai_texts[-1].lower() if ai_texts else ""
    last_user_low = user_texts[-1].strip().lower() if user_texts else ""
    if last_ai and any(c in last_ai for c in _MEETING_CTX) and (
        last_user_low in _AFFIRMATIVE or any(last_user_low.startswith(a + " ") for a in _AFFIRMATIVE)
    ):
        facts["scheduling_confirmed"] = "yes"
    _PT_VARIANT_HINTS = {
        "pt-PT": ["portugal", "português de portugal", "pt-pt", "pt portugal", "portugal pt", "pt europeu", "europeu"],
        "pt-BR": ["brasil", "brazil", "português do brasil", "pt-br", "pt brasil", "brasileiro"],
        "pt-AO": ["angola", "angolano"],
        "pt-MZ": ["moçambique", "mocambique", "moçambicano", "mocambicano"],
        "pt-CV": ["cabo verde", "cabo-verdiano"],
    }
    for t in user_texts:
        tl = t.lower()
        for variant, hints in _PT_VARIANT_HINTS.items():
            if any(h in tl for h in hints):
                facts["language_variant"] = variant
                break
        if "language_variant" in facts:
            break

    # Sinaliza pedido de tradução para PT sem variante indicada — a AI deve perguntar.
    _PT_TRANSLATION_ASK = (
        "traduzir para portugu", "tradução para portugu", "traducao para portugu",
        "traduzir o site para portugu", "conteúdo em portugu", "conteudo em portugu",
        "quero em portugu", "site em portugu", "versão em portugu", "versao em portugu",
        "quero portugu", "para portugu",
    )
    last_user = user_texts[-1].lower() if user_texts else ""
    if any(k in last_user for k in _PT_TRANSLATION_ASK) and "language_variant" not in facts:
        facts["ask_pt_variant"] = "yes"

    # Já perguntámos a variante? (para não repetir)
    for t in ai_texts:
        tl = t.lower()
        if "portugu" in tl and ("portugal" in tl and "brasil" in tl):
            facts["pt_variant_asked"] = "yes"
            break

    # Pergunta de utilizadores/equipa foi colocada pela AI?
    # Lista alargada para cobrir TODAS as variações naturais que a Maria/agentes
    # podem usar quando perguntam sobre dimensão da equipa.
    asked_users = False
    _USER_QUESTION_KEYWORDS = (
        "quantos utilizadores", "quantos usuarios", "quantos colaboradores",
        "quantos agentes", "quantas pessoas", "quantos sao", "quantos são",
        "tamanho da equipa", "tamanho da tua", "tamanho da sua",
        "elementos na equipa", "elementos da equipa",
        "sois quantos", "são quantos",
        "sozinho ou com", "sozinha ou com",
        "tu sozinho", "tu sozinha", "trabalhas sozinho", "trabalhas sozinha",
        "equipa pequena", "equipa grande",
        "número de utilizadores", "numero de utilizadores",
        "quantos vão usar", "quantos vao usar",
    )
    for m in history or []:
        if m.get("sender") == "ai":
            t = (m.get("text") or "").lower()
            if any(k in t for k in _USER_QUESTION_KEYWORDS):
                asked_users = True
                break

    for t in user_texts:
        if not t:
            continue
        # Users count — só consideramos válido se a pergunta foi feita ou
        # se a frase tem palavra-chave 'utilizador/pessoa/equipa'
        if "users" not in facts:
            n = _extract_users_count(t)
            if n is not None:
                # Se for resposta ultra-curta ("eu", "um", "1"), só aceitar se a AI perguntou antes
                ultra_short = len(t.strip().split()) <= 3
                has_keyword = any(k in t.lower() for k in (
                    "utilizador", "pessoa", "equipa", "colaborador", "agente", "user"))
                if has_keyword or (ultra_short and asked_users):
                    facts["users"] = str(n)

        # Sector
        if "sector" not in facts:
            s = _extract_sector(t)
            if s:
                facts["sector"] = s

        # Name
        if "name" not in facts:
            n = _extract_name(t)
            if n:
                facts["name"] = n

        # Email
        if "email" not in facts:
            m = _EMAIL_RE.search(t)
            if m:
                facts["email"] = m.group(0)

        # Phone
        if "phone" not in facts:
            m = _PHONE_RE.search(t)
            if m:
                facts["phone"] = m.group(0)

    return facts


def format_facts_pt(facts: Dict[str, str]) -> str:
    """Constrói bloco 'JÁ SABEMOS:' para injectar no prompt.
    A primeira linha é um HARD-GUARDRAIL destacado — o LLM tende a ignorar
    blocos genéricos, mas obedece a instruções em caixa-alta com ⛔."""
    if not facts:
        return ""
    lines = []
    if "name" in facts:    lines.append(f"- Nome: {facts['name']}")
    if "sector" in facts:  lines.append(f"- Setor: {facts['sector']}")
    if "users" in facts:   lines.append(f"- Nº de utilizadores: {facts['users']}")
    if "email" in facts:   lines.append(f"- Email: {facts['email']}")
    if "phone" in facts:   lines.append(f"- Telefone: {facts['phone']}")
    flags = []
    if facts.get("pricing_shown") == "yes":
        flags.append("- ⚠️ Planos JÁ apresentados — NÃO voltar a listar (só responder a pergunta específica)")
    if facts.get("demo_link_shared") == "yes":
        flags.append("- ⚠️ Link de agendamento JÁ partilhado — NÃO insistir; só repetir se o utilizador pedir")
    if facts.get("language_variant"):
        flags.append(f"- 🌐 Variante PT confirmada: {facts['language_variant']} — NÃO voltar a perguntar")
    if facts.get("pt_variant_asked") == "yes" and not facts.get("language_variant"):
        flags.append("- 🌐 Já perguntámos a variante PT nesta conversa — se o utilizador ainda não escolheu, aguarda; NÃO voltes a perguntar.")
    if facts.get("ask_pt_variant") == "yes" and not facts.get("language_variant") and facts.get("pt_variant_asked") != "yes":
        flags.append("- 🌐 ⚠️ O utilizador pediu tradução para 'português' SEM variante — PERGUNTA obrigatoriamente qual pretende (Portugal, Brasil, outra) antes de avançar.")
    if not lines and not flags:
        return ""

    # HARD GUARDRAIL — enumerated forbidden re-asks
    forbid = []
    if "users" in facts:
        forbid.append(f'❌ "quantos utilizadores/pessoas/colaboradores/agentes?" — JÁ SABES: {facts["users"]}. Se te apetecer perguntar isto, PARA e usa o número acima.')
    if "name" in facts:
        forbid.append(f'❌ "como te chamas?" / "qual o teu nome?" — JÁ SABES: {facts["name"]}.')
    if "email" in facts:
        forbid.append(f'❌ "qual o teu email?" — JÁ SABES: {facts["email"]}.')
    if "sector" in facts:
        forbid.append(f'❌ "que setor / que área / imobiliária ou hotel?" — JÁ SABES: {facts["sector"]}.')
    if "phone" in facts:
        forbid.append(f'❌ "qual o teu telefone?" — JÁ SABES: {facts["phone"]}.')

    out = []
    if forbid:
        out.append(
            "⛔ CAMPOS JÁ CAPTURADOS — PROIBIDO VOLTAR A PERGUNTAR:\n"
            + "\n".join(forbid)
            + "\n\n👉 Usa estes valores DIRETAMENTE na tua resposta e AVANÇA para o próximo passo (proposta de plano, link de demo, próxima pergunta diferente). "
              "NUNCA reformules a mesma pergunta com palavras diferentes. NUNCA digas 'para confirmar' ou 'peço desculpa pela confusão'."
        )
    if lines:
        out.append("JÁ SABEMOS DO UTILIZADOR:\n" + "\n".join(lines))
    if flags:
        out.append("ESTADO DA CONVERSA:\n" + "\n".join(flags))
    return "\n\n".join(out)
