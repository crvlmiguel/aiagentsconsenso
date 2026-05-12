import React from "react";

/**
 * Public landing-style demo pages — no auth required.
 * Each demo loads the Consenso widget for a specific agent so prospects can
 * try the AI live without signup. The hero showcases the use-case for that
 * sector, the right column embeds the widget iframe.
 */

const TENANT_ID = "b63f7593-d59a-491d-8c91-e28caea3f760";

// Agent IDs (Maria tenant). Update if seed regenerates ids.
const AGENTS = {
  generalista: "4b4dbf03-2107-473a-b578-9456ad2a9318",     // Maria — multissetorial
  hotelaria:   "dcb8ef3e-e87b-4437-87d2-c271bf44ad5a",     // StayLocal Concierge (AL/Hotelaria)
  turismo:     "bc8ed7a6-d528-40ef-9665-09e05ecfe9fc",     // Tejo Sunset Sailing AI Guide
};

const PRESETS = {
  generalista: {
    eyebrow: "DEMO MULTISSETORIAL",
    title: "Maria — Assistente IA da Consenso",
    subtitle: "Para qualquer setor: imobiliário, hotelaria, clínicas, restauração, e-commerce, serviços e mais.",
    bullets: [
      { i: "🌍", t: "6 idiomas automáticos", s: "PT · EN · FR · DE · ES · NL com deteção em tempo real" },
      { i: "🧠", t: "Adapta-se ao teu setor", s: "Identifica o contexto e mostra casos de uso relevantes" },
      { i: "💬", t: "Multicanal", s: "Webchat · WhatsApp · Instagram · Facebook · Telegram" },
      { i: "📅", t: "Marca demos automaticamente", s: "Integração Google Calendar e link de reunião" },
    ],
    ctas: ["Fala comigo sobre a Consenso", "Que setores serves?", "Quanto custa?", "Marcar uma demo"],
    agentKey: "generalista",
    accent: "#4591CE",
  },
  hotelaria: {
    eyebrow: "DEMO HOTELARIA / ALOJAMENTO LOCAL",
    title: "Concierge IA para Hotéis e AL",
    subtitle: "Reservas, FAQs, check-ins e upselling em 6 idiomas, 24/7 — sem sobrecarregar a tua receção.",
    bullets: [
      { i: "🛎️", t: "Reservas multilíngua 24/7", s: "Aceita pedidos enquanto a receção dorme" },
      { i: "🔄", t: "Integra com o teu PMS", s: "Mostra disponibilidade real e sincroniza" },
      { i: "⭐", t: "Reviews mais altas", s: "Hóspedes alemães respondidos às 3h da manhã" },
      { i: "📉", t: "Menos no-shows", s: "Lembretes WhatsApp automáticos" },
    ],
    ctas: ["Quero ver uma reserva", "Recomenda restaurantes na zona", "O check-in é a que horas?", "Quero falar com um humano"],
    agentKey: "hotelaria",
    accent: "#E4AC1E",
  },
  turismo: {
    eyebrow: "DEMO TURISMO",
    title: "Agente IA para Turismo e Experiências",
    subtitle: "Tours, atividades e pré-reservas em conversação natural — converte visitantes do site em hóspedes pagos.",
    bullets: [
      { i: "🗺️", t: "Recomenda experiências", s: "Adaptado ao perfil e idioma do turista" },
      { i: "🌐", t: "6 idiomas em tempo real", s: "Sem ter de contratar guias multilingue" },
      { i: "💳", t: "Pré-reservas integradas", s: "Capta o lead com cartão antes de fechar" },
      { i: "⛵", t: "Sazonalidade gerida", s: "Funciona melhor justamente fora de época" },
    ],
    ctas: ["What experiences do you offer?", "Quanto custa o tour ao pôr-do-sol?", "Tenho 4 pessoas, disponibilidade sexta?", "Falas alemão?"],
    agentKey: "turismo",
    accent: "#0EA5E9",
  },
};

function DemoLayout({ preset }) {
  const widgetUrl = `${process.env.REACT_APP_BACKEND_URL}/api/widget/${TENANT_ID}?agent=${AGENTS[preset.agentKey]}`;

  return (
    <div style={{ minHeight: "100vh", background: "#F7F9FC", fontFamily: "Inter, system-ui, sans-serif", color: "#0B1324" }}>
      <header style={{ borderBottom: "1px solid #E5EAF2", background: "#fff" }}>
        <div style={{ maxWidth: 1200, margin: "0 auto", padding: "18px 24px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, fontWeight: 700, letterSpacing: -0.2 }}>
            <span style={{ background: preset.accent, color: "#fff", padding: "5px 10px", borderRadius: 8, fontSize: 13 }}>Consenso+</span>
            <span style={{ fontSize: 14, color: "#5B6B82" }}>{preset.eyebrow}</span>
          </div>
          <a href="https://consenso-shop.eu/marcar-reuniao" target="_blank" rel="noopener noreferrer"
             style={{ background: "#E4AC1E", color: "#fff", padding: "9px 18px", borderRadius: 999, textDecoration: "none", fontSize: 13, fontWeight: 600, boxShadow: "0 3px 10px rgba(228,172,30,.32)" }}
             data-testid="cta-marcar-reuniao">
            Marcar reunião
          </a>
        </div>
      </header>

      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "48px 24px", display: "grid", gridTemplateColumns: "1.1fr 1fr", gap: 56, alignItems: "start" }}>
        <section>
          <div style={{ display: "inline-block", background: preset.accent + "1A", color: preset.accent, padding: "5px 12px", borderRadius: 999, fontSize: 11, fontWeight: 700, letterSpacing: 0.6, textTransform: "uppercase", marginBottom: 20 }}>
            {preset.eyebrow}
          </div>
          <h1 style={{ fontSize: 44, lineHeight: 1.1, letterSpacing: -1, margin: "0 0 18px", fontWeight: 800 }}>
            {preset.title}
          </h1>
          <p style={{ fontSize: 17, color: "#5B6B82", margin: "0 0 32px", lineHeight: 1.55 }}>
            {preset.subtitle}
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 36 }}>
            {preset.bullets.map((b, i) => (
              <div key={i} style={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 14, padding: "16px 16px 14px" }}>
                <div style={{ fontSize: 22, marginBottom: 6 }}>{b.i}</div>
                <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 3 }}>{b.t}</div>
                <div style={{ fontSize: 12, color: "#5B6B82", lineHeight: 1.4 }}>{b.s}</div>
              </div>
            ))}
          </div>

          <div style={{ background: "#fff", border: "1px solid #E5EAF2", borderRadius: 14, padding: 18 }}>
            <div style={{ fontSize: 12, color: "#8593A8", textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 600, marginBottom: 10 }}>
              👉 Experimenta agora ao lado
            </div>
            <div style={{ fontSize: 13, color: "#5B6B82", lineHeight: 1.5 }}>
              Tenta perguntas como:
              <ul style={{ paddingLeft: 18, margin: "8px 0 0" }}>
                {preset.ctas.map((c, i) => (
                  <li key={i} style={{ marginBottom: 4 }}><em>"{c}"</em></li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section style={{ position: "sticky", top: 24 }}>
          <div style={{ background: "#fff", borderRadius: 18, boxShadow: "0 12px 40px rgba(11,19,36,.10)", overflow: "hidden", border: "1px solid #E5EAF2" }}>
            <iframe
              src={widgetUrl}
              title={`Consenso ${preset.agentKey} demo`}
              style={{ width: "100%", height: 680, border: 0, display: "block" }}
              data-testid={`demo-widget-${preset.agentKey}`}
              allow="clipboard-write"
            />
          </div>
          <div style={{ marginTop: 14, textAlign: "center", fontSize: 12, color: "#8593A8" }}>
            Powered by <strong style={{ color: preset.accent }}>Consenso+</strong> · IA empresarial para o mercado português
          </div>
        </section>
      </main>

      <footer style={{ borderTop: "1px solid #E5EAF2", padding: "24px", textAlign: "center", color: "#5B6B82", fontSize: 13, background: "#fff" }}>
        © {new Date().getFullYear()} Consenso Global · ISO 9001 · 17100 · 18587 · 27001 ·
        <a href="https://consenso-shop.eu" target="_blank" rel="noopener noreferrer" style={{ color: preset.accent, marginLeft: 4 }}>consenso-shop.eu</a>
      </footer>
    </div>
  );
}

export function DemoGeneralista() { return <DemoLayout preset={PRESETS.generalista} />; }
export function DemoHotelaria()   { return <DemoLayout preset={PRESETS.hotelaria} />; }
export function DemoTurismo()     { return <DemoLayout preset={PRESETS.turismo} />; }

export default DemoLayout;
