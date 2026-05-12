"""Helper to format page_context hint for Maria's system prompt.
Used by both generate_response and generate_response_stream."""


_AREA_MAP = {
    "imobiliario": "🏠 IMOBILIÁRIO — o visitante está na página de Imobiliário. Foca em portefólios, visitas, crédito habitação.",
    "imobiliario_pt": "🏠 IMOBILIÁRIO",
    "hotelaria":   "🛎️ HOTELARIA — o visitante está na página de Hotelaria. Foca em reservas, PMS, multi-idioma, upselling.",
    "turismo":     "🌍 TURISMO — o visitante está na página de Turismo. Foca em tours, experiências, bookings, multi-idioma.",
    "servicos":    "💼 EMPRESAS DE SERVIÇOS — o visitante está na página de Serviços. Foca em qualificação de leads, atendimento, FAQs.",
    "servicos_empresas": "💼 EMPRESAS DE SERVIÇOS — o visitante está na página de Serviços. Foca em qualificação de leads, atendimento, FAQs.",
    "geral":       "ℹ️ HOMEPAGE — o visitante está na homepage; não assumas área específica.",
}


def page_context_block(page_context: str) -> str:
    """Return a 1-line block to inject into the system prompt, or empty string."""
    if not page_context:
        return ""
    key = (page_context or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in _AREA_MAP:
        return f"CONTEXTO DA PÁGINA: {_AREA_MAP[key]}"
    return f"CONTEXTO DA PÁGINA: {page_context[:60]}"
