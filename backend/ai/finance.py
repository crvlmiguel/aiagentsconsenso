"""Simulação de crédito habitação — cálculo de prestação mensal usando fórmula PMT.

Pode ser chamado pela Maria/agentes IA quando o cliente pergunta sobre
prestações, financiamento ou crédito habitação.
"""
import re
from typing import Optional


# Taxa Euribor 12 meses (atualizar manualmente trimestralmente)
EURIBOR_12M_DEFAULT = 2.45  # Em % — fev 2026
SPREAD_DEFAULT = 1.20       # Spread médio dos bancos PT


def _to_float(value, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        s = re.sub(r"[^\d.,]", "", str(value)).replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return default


def calcular_prestacao(
    valor_imovel: float,
    entrada_pct: float = 20.0,
    prazo_anos: int = 30,
    euribor: float = EURIBOR_12M_DEFAULT,
    spread: float = SPREAD_DEFAULT,
    idade: Optional[int] = None,
) -> dict:
    """Calcula a prestação mensal de um crédito habitação (fórmula PMT).

    Args:
        valor_imovel: preço do imóvel em euros
        entrada_pct: percentagem de entrada (default 20%)
        prazo_anos: prazo do crédito em anos (default 30, máx 40)
        euribor: taxa Euribor 12m em % (default 2.45)
        spread: spread do banco em % (default 1.20)
        idade: idade do cliente — se fornecida, limita o prazo a (80 - idade)

    Returns:
        dict com: valor_imovel, entrada, montante, taxa_total, prazo_meses,
                  prestacao_mensal, total_pago, juros_totais, idade, prazo_max_bancario
    """
    valor_imovel = max(_to_float(valor_imovel), 1)
    entrada_pct = max(min(_to_float(entrada_pct, 20.0), 100.0), 0.0)
    prazo_anos = max(min(int(_to_float(prazo_anos, 30)), 40), 5)
    euribor = max(_to_float(euribor, EURIBOR_12M_DEFAULT), 0.0)
    spread = max(_to_float(spread, SPREAD_DEFAULT), 0.0)

    # Aplicar limite bancário (80 - idade) se idade fornecida
    prazo_max_bancario = None
    idade_clean = None
    if idade is not None:
        try:
            idade_clean = max(min(int(idade), 80), 18)
            prazo_max_bancario = max(80 - idade_clean, 5)
            if prazo_anos > prazo_max_bancario:
                prazo_anos = prazo_max_bancario
        except (TypeError, ValueError):
            pass

    entrada = valor_imovel * (entrada_pct / 100.0)
    montante = valor_imovel - entrada
    taxa_anual = (euribor + spread) / 100.0
    taxa_mensal = taxa_anual / 12.0
    n_meses = prazo_anos * 12

    if taxa_mensal == 0:
        prestacao = montante / n_meses
    else:
        prestacao = montante * (taxa_mensal * (1 + taxa_mensal) ** n_meses) / \
                    ((1 + taxa_mensal) ** n_meses - 1)

    total_pago = prestacao * n_meses
    juros_totais = total_pago - montante

    return {
        "valor_imovel": round(valor_imovel, 2),
        "entrada_pct": round(entrada_pct, 1),
        "entrada": round(entrada, 2),
        "montante_credito": round(montante, 2),
        "euribor_pct": round(euribor, 3),
        "spread_pct": round(spread, 3),
        "taxa_total_pct": round((euribor + spread), 3),
        "prazo_anos": prazo_anos,
        "prazo_meses": n_meses,
        "prestacao_mensal": round(prestacao, 2),
        "total_pago": round(total_pago, 2),
        "juros_totais": round(juros_totais, 2),
        "idade": idade_clean,
        "prazo_max_bancario": prazo_max_bancario,
    }


# ===== Extração de parâmetros de crédito do histórico de conversa =====
# Regex rigorosas — requerem keyword explícita para evitar ambiguidade "X anos"
_ENTRADA_RE = re.compile(
    r"(?:entrada|sinal|down\s*payment)\s*(?:de\s+|:?\s*)?"
    r"(?:de\s+)?(\d{1,3}(?:[.,]\d+)?)\s*%",
    re.IGNORECASE,
)
_ENTRADA_PCT_RE = re.compile(
    r"(\d{1,3}(?:[.,]\d+)?)\s*%\s*(?:de\s+)?(?:entrada|sinal)",
    re.IGNORECASE,
)
_PRAZO_RE = re.compile(
    r"(?:prazo|durante|período|periodo|por|a)\s*(?:de\s+)?(\d{1,2})\s*anos?(?!\s*(?:de\s*)?idade)|"
    r"(\d{1,2})\s*anos?\s*(?:de\s*prazo|de\s*cr[ée]dito|de\s*hipoteca|de\s*emprestim)",
    re.IGNORECASE,
)
_IDADE_RE = re.compile(
    r"(?:tenho|sou|com|aged?)\s+(\d{2})\s*anos?(?!\s*(?:de\s*prazo|de\s*cr[ée]dito))|"
    r"(\d{2})\s*anos?\s+de\s+idade|"
    r"idade\s*(?::|\-|de)?\s*(\d{2})",
    re.IGNORECASE,
)


def extract_credit_params(text: str) -> dict:
    """Extrai entrada/prazo/idade de texto livre. Devolve dict com chaves opcionais.
    As regex requerem keyword explícita para evitar ambiguidade entre prazo e idade."""
    out = {}
    if not text:
        return out
    t = text.lower()

    # Entrada — duas variantes ("entrada de 20%" e "20% de entrada")
    for rgx in (_ENTRADA_RE, _ENTRADA_PCT_RE):
        m = rgx.search(t)
        if m:
            val_str = (m.group(1) or "").replace(",", ".")
            try:
                v = float(val_str)
                if 1 <= v <= 100:
                    out["entrada_pct"] = v
                    break
            except ValueError:
                pass

    m = _PRAZO_RE.search(t)
    if m:
        val_str = m.group(1) or m.group(2) or ""
        try:
            v = int(val_str)
            if 5 <= v <= 40:
                out["prazo_anos"] = v
        except ValueError:
            pass

    m = _IDADE_RE.search(t)
    if m:
        val_str = m.group(1) or m.group(2) or m.group(3) or ""
        try:
            v = int(val_str)
            if 18 <= v <= 75:
                out["idade"] = v
        except ValueError:
            pass

    return out


# ===== Detecção de intenção financeira =====
_FINANCE_INTENT_RE = re.compile(
    r"\b(presta[çc][ãa]o|cr[ée]dito habita|cr[ée]dito hipotec|hipoteca|mortgage|"
    r"financiamento|euribor|spread|simula(?:r|[çc][ãa]o)|"
    r"quanto (?:fica|paga|custa)|"
    r"mensalidade do (?:cr[ée]dito|im[óo]vel|emprestim)|"
    r"comprar com cr[ée]dito|comprar a cr[ée]dito|"
    r"mensalit|monthly payment|loan calc)",
    re.IGNORECASE,
)

# Match "1.450.000 €", "780000€", "350 000 EUR", "500k", "1.5M", "500 mil"
_PRICE_RE = re.compile(
    r"(\d{1,3}(?:[.\s]\d{3})+|\d+(?:[.,]\d+)?)\s*(?:€|EUR|euros?|k|mil|m\b|milh)",
    re.IGNORECASE,
)


def detect_finance_intent(text: str) -> bool:
    return bool(_FINANCE_INTENT_RE.search(text or ""))


def extract_price_from_text(text: str) -> Optional[float]:
    """Extrai um valor monetário do texto (suporta 500k, 1.5M, 350 000€, 780000€)."""
    if not text:
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = m.group(1).replace(" ", "").replace(".", "")
    # Se tem vírgula como decimal (PT)
    if "," in raw:
        raw = raw.replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        return None
    suffix = (m.group(0)[len(m.group(1)):] or "").strip().lower()
    if "k" in suffix or "mil" in suffix:
        value *= 1000
    elif suffix.startswith("m") or "milh" in suffix:
        value *= 1_000_000
    return value


def format_simulation_pt(sim: dict) -> str:
    """Formata o resultado da simulação em texto para o widget (PT-PT)."""
    return (
        f"💡 Simulação de crédito habitação\n\n"
        f"🏠 Imóvel: {sim['valor_imovel']:,.0f} €\n"
        f"💶 Entrada ({sim['entrada_pct']:.0f}%): {sim['entrada']:,.0f} €\n"
        f"📊 Montante: {sim['montante_credito']:,.0f} € a {sim['prazo_anos']} anos\n"
        f"📈 Taxa total: {sim['taxa_total_pct']:.2f}% (Euribor {sim['euribor_pct']:.2f}% + Spread {sim['spread_pct']:.2f}%)\n\n"
        f"➡️  Prestação mensal: **{sim['prestacao_mensal']:,.2f} €**\n"
        f"💰 Total pago: {sim['total_pago']:,.0f} € (juros: {sim['juros_totais']:,.0f} €)"
    ).replace(",", " ")  # PT-PT thousands separator
