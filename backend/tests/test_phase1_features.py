"""Tests for new Phase 1 features:
- Finance simulation (calcular_prestacao, intent detection, price extraction)
- Lead Scoring 0-100
- Property Feed CSV/XML parsers
- Multi-language reply (smoke test via integration with /webchat endpoint)
"""
import pytest
from ai.finance import (
    calcular_prestacao, detect_finance_intent,
    extract_price_from_text, format_simulation_pt,
)
from ai.lead_score import compute_lead_score
from property_feed import parse_csv, parse_xml


# ============================================================================
# FINANCE SIMULATION
# ============================================================================

def test_finance_simulation_basic():
    sim = calcular_prestacao(500000, entrada_pct=20, prazo_anos=30)
    assert sim["valor_imovel"] == 500000
    assert sim["entrada"] == 100000
    assert sim["montante_credito"] == 400000
    assert sim["prazo_anos"] == 30
    # Prestação at ~3.65% over 30 years on 400k should be ~1830 €
    assert 1700 < sim["prestacao_mensal"] < 1900
    assert sim["total_pago"] > sim["montante_credito"]


def test_finance_simulation_clamps():
    """Prazo limita-se a 5-40 anos."""
    sim = calcular_prestacao(100000, prazo_anos=50)
    assert sim["prazo_anos"] == 40
    sim2 = calcular_prestacao(100000, prazo_anos=2)
    assert sim2["prazo_anos"] == 5


def test_finance_simulation_zero_entrada():
    """Sem entrada (100% financiamento)."""
    sim = calcular_prestacao(300000, entrada_pct=0, prazo_anos=25)
    assert sim["entrada"] == 0
    assert sim["montante_credito"] == 300000


def test_detect_finance_intent_pt():
    assert detect_finance_intent("quanto fica a prestação?")
    assert detect_finance_intent("queria simular crédito habitação")
    assert detect_finance_intent("hipoteca para um T2")
    assert detect_finance_intent("mortgage calculator please")
    assert not detect_finance_intent("olá tudo bem")
    assert not detect_finance_intent("quero ver imóveis em lisboa")


def test_extract_price_various_formats():
    assert extract_price_from_text("custa 500000€") == 500000.0
    assert extract_price_from_text("o apartamento é 500k") == 500000.0
    assert extract_price_from_text("1.450.000 €") == 1450000.0
    assert extract_price_from_text("780 000 EUR") == 780000.0
    assert extract_price_from_text("olá") is None


def test_format_simulation_returns_pt_string():
    sim = calcular_prestacao(500000)
    text = format_simulation_pt(sim)
    assert "Simulação" in text
    assert "€" in text
    assert "Prestação mensal" in text


# ============================================================================
# LEAD SCORING
# ============================================================================

def test_lead_score_cold():
    r = compute_lead_score(history=[{"sender": "user", "text": "Olá"}])
    assert r["score"] < 40
    assert r["tier"] == "frio"


def test_lead_score_warm():
    r = compute_lead_score(
        conversation={"qualification": {
            "lead": {"name": "Ana", "email": "ana@t.com"},
            "search": {"property_type": "T2", "zone": "Lisboa"},
        }},
        lead={"name": "Ana", "email": "ana@t.com"},
        history=[{"sender": "user", "text": "T2 em Lisboa"}],
    )
    assert 40 <= r["score"] < 70
    assert r["tier"] == "morno"


def test_lead_score_hot():
    r = compute_lead_score(
        conversation={"qualification": {
            "lead": {"name": "Carlos", "email": "c@t.com"},
            "search": {"property_type": "V4", "zone": "Cascais"},
            "budget": "até 2M", "status": "visita_agendada", "profile": "Investidor",
        }},
        lead={"name": "Carlos", "email": "c@t.com", "phone": "+351911",
              "tags": ["visita-marcada"]},
        history=[{"sender": "user", "text": f"msg {i}"} for i in range(8)] + [
            {"sender": "user", "text": "preciso urgente"}],
    )
    assert r["score"] >= 70
    assert r["tier"] == "quente"


def test_lead_score_clamps_to_100():
    """Mesmo com muitos sinais, score nunca passa de 100."""
    r = compute_lead_score(
        conversation={"qualification": {
            "lead": {"name": "X", "email": "x@y.com"},
            "search": {"property_type": "V99", "zone": "Z"},
            "budget": "1B", "status": "visita_agendada", "profile": "Investidor",
        }},
        lead={"name": "X", "email": "x@y.com", "phone": "+1", "tags": ["visita-marcada"]},
        history=[{"sender": "user", "text": "urgente"} for _ in range(20)],
    )
    assert r["score"] <= 100


# ============================================================================
# PROPERTY FEED PARSERS
# ============================================================================

CSV_SAMPLE = """title,price,location,typology,area_m2,image,link,description
Apartamento T3 Estoril,650000 EUR,Estoril,T3,140,https://x.com/img1.jpg,https://idealista.pt/imovel/123,Apartamento renovado
Moradia V4 Sintra,890000 EUR,Sintra,V4,280,https://x.com/img2.jpg,https://imovirtual.com/345,Moradia com jardim
"""


def test_parse_csv():
    items = parse_csv(CSV_SAMPLE)
    assert len(items) == 2
    assert items[0]["title"] == "Apartamento T3 Estoril"
    assert items[0]["typology"] == "T3"
    assert items[0]["area_m2"] == 140
    assert items[1]["location"] == "Sintra"


def test_parse_csv_pt_columns():
    """Aceita colunas em PT (titulo, preco, zona, etc.)."""
    csv_pt = """titulo,preco,zona,tipologia
Casa Lagos,300000 EUR,Lagos,T2"""
    items = parse_csv(csv_pt)
    assert len(items) == 1
    assert items[0]["title"] == "Casa Lagos"
    assert items[0]["location"] == "Lagos"


def test_parse_xml_basic():
    xml = """<?xml version="1.0"?>
<feed>
  <item>
    <title>Apartment Lisboa</title>
    <price>450000 EUR</price>
    <location>Lisboa</location>
    <typology>T2</typology>
    <link>https://example.com/1</link>
  </item>
</feed>"""
    items = parse_xml(xml)
    assert len(items) == 1
    assert items[0]["title"] == "Apartment Lisboa"
    assert items[0]["typology"] == "T2"


def test_parse_csv_empty_returns_empty():
    assert parse_csv("") == []


def test_parse_csv_invalid_skip():
    """Linhas sem título devem ser ignoradas."""
    csv = """title,price
,100€
Casa Real,200€"""
    items = parse_csv(csv)
    assert len(items) == 1
    assert items[0]["title"] == "Casa Real"
