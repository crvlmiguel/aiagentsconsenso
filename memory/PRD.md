# Consenso Plus — PRD (v2.0)

**Pivot v2:** PT-PT UI, light-mode design (#0069FE Stripe/Intercom), Chatbot Builder, Data Sources, structured cards, WebSocket live chat, embeddable widget.

## Arquitetura
- **Backend FastAPI v2.0**: `server.py`, `auth.py`, `models.py`, `ai/{router,intent,structure,orchestrator,tools,retrieval}.py`, `ws_manager.py`, `seed.py`
- **Frontend React 19**: light mode branded UI. Rotas PT: `/iniciar-sessao`, `/registar`, `/app/{painel,caixa,construtor,agentes,fontes,leads,tickets,canais,equipa,admin,definicoes}`

## Implementado (2026-05-03 v2.0)
- Auth multi-tenant (JWT + bcrypt)
- Pipeline AI: intent → structure → retrieval (keyword sobre chunks das fontes) → orchestrator → router multi-LLM (OpenAI/Claude/Gemini via `emergentintegrations` + Emergent LLM Key) → ferramentas → resposta **{reply, cards[], language}**
- Deteção automática de idioma (langdetect); resposta obrigatória em Português Europeu
- Caixa de entrada 3-painéis estilo Intercom com WebSocket live
- Construtor (wizard 4 passos: Modelo → Instruções → Dados → Ativar) com 4 templates (Imobiliária, Suporte, E-commerce, Clínica)
- Agentes IA CRUD + tester "Executar pipeline completo"
- **Fontes de dados**: URL scraping (BeautifulSoup, heurística items/cards), texto inline, reindexação
- **Cards estruturados**: AI devolve title/price/image/link renderizados como cards no chat + widget
- Leads com tags, score, CRM sync (stub)
- Tickets, Canais & CRM, Equipa, Admin, Definições (com snippet de incorporação iframe)
- Widget de chat ao vivo embutível em `/api/widget/{tenant_id}` — HTML standalone com estilo próprio, fala com `/api/webchat/{tenant_id}/message`

## Seed (PT-PT)
Tenant "Imobiliária Lisboa", owner Maria Silva (demo@consenso.plus / demo1234), agente "Aria — Assistente Imobiliária" ligada à fonte "Catálogo de imóveis (demo)" com 4 imóveis; 3 conversas (Ana, João, Rita) nos canais webchat/whatsapp/instagram; 1 lead, 1 ticket, 10 integrações (5 canais + 4 CRM + 1 email).

## Testing subagent (iteração 2)
- Backend: **19/19 testes pass** (incluindo AI pipeline com cards, deteção de idioma, CRUD de fontes, WebSocket, widget)
- Frontend: ~90% validado. Problemas corrigidos:
  - HIGH: snippet embed usava `/widget/` sem prefixo `/api` → apanhado pelo ingress → corrigido em Definicoes.jsx
  - MEDIUM: pie chart com sizing race → min-height + fallback empty state
  - LOW: WS fechava em double-mount StrictMode → delay + cleanup-safe

## Backlog P0
- Real integrations: Telegram Bot webhook, WhatsApp Cloud webhook
- File upload real (object storage) para PDFs/DOCX
- Rate limiting no /api/webchat público

## Backlog P1
- Vector embeddings (Mongo Atlas Search) em vez de keyword match
- CRM sync real (HubSpot OAuth, Pipedrive API)
- SMTP envio real
- Multi-agente por tenant com routing por regras

## Backlog P2
- Workflow builder visual
- Stripe usage billing (tokens/tenant)
- SLA nos tickets
- Split `server.py` em routers (já >700 linhas)
