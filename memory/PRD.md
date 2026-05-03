# Consenso Plus — Product Requirements Document

**Original problem statement:** Build a production-grade multi-tenant SaaS "CONSENSO PLUS — AI Business Operating System". NOT a marketing site — only the application. Unified inbox across WhatsApp/Instagram/Telegram/Messenger/Web Chat, AI agents that respond automatically, intent + structure engines, multi-LLM routing (OpenAI/Claude/Gemini), leads/tickets/integrations/team/admin modules.

## User choices (defaults)
- Scope: Auth + multi-tenant + Unified Inbox + AI Agents + Web Chat Widget + simulated other channels
- AI: Emergent Universal LLM Key (OpenAI, Anthropic, Gemini)
- Memory: MongoDB (no pgvector)
- CRMs: Generic webhook + UI-only stubs

## Architecture
- **Backend**: FastAPI + Motor Mongo. `server.py` with `auth.py`, `models.py`, `ai/{router,intent,structure,orchestrator,tools}.py`, `seed.py`
- **Frontend**: React 19 + Tailwind + shadcn. Dark brutalist (`rounded-none`, `#FF5500` AI accent, Chivo + JetBrains Mono). Routes: `/login`, `/register`, `/app/{inbox,agents,leads,tickets,integrations,analytics,team,admin,settings}`.

## What's implemented (2026-05-03)
- JWT auth, bcrypt, multi-tenant data isolation
- Full AI pipeline: intent → structure → orchestrator → multi-LLM router (via `emergentintegrations`) → tool execution → reply storage
- Unified Inbox (3-pane Intercom-style): list + thread + AI analysis/simulator panel
- Conversation: takeover / release / close / tag, real-time human chat, AI pauses on human takeover
- Agents CRUD + live `RUN FULL PIPELINE` tester (returns intent/structure/decision/reply JSON)
- Leads CRUD with stage dropdown + score progress
- Tickets CRUD with priority + status
- Integrations: 5 channels + 4 CRM stubs with connect/disconnect toggle
- Analytics: KPI grid + channel bar chart + lead stage pie chart
- Team invite + remove
- Platform Admin page (restricted to `platform_admin` role)
- Settings: workspace info, webchat endpoint, embed snippet, model registry
- Public webchat endpoint `/api/webchat/{tenant_id}/message`
- Authenticated simulator `/api/inbound/simulate`
- Seed script creates demo tenant `demo@consenso.plus / demo1234` (Acme Corp) with 3 conversations, agent "Aria", integrations

## Test credentials
- `demo@consenso.plus` / `demo1234` (owner of Acme Corp)

## P0 backlog (next)
- WebSocket-based real-time inbox updates
- Real WhatsApp Cloud webhook + Telegram Bot inbound
- Embeddable Web Chat widget (iframe or JS SDK)
- Vector memory for agent knowledge (Mongo Atlas Search or embeddings)

## P1 backlog
- Knowledge base files (upload via object storage)
- OAuth CRM wiring (HubSpot, Pipedrive, Salesforce)
- Per-agent routing rules (tags → agent)
- Audit log + role-based permissions beyond owner/admin/agent

## P2 backlog
- Workflow builder UI
- SLA policies for tickets
- Email channel
- Usage-based billing (Stripe)
