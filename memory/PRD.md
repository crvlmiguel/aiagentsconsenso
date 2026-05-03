# Consenso Plus — PRD (v2.3)

## v2.3 (2026-05-03) — Identidade do agente + canais por agente + widget Intercom-style

### Novidades
- **Identidade do agente**: `avatar_url`, `welcome_message`, `icebreakers[]` editáveis na página Agentes IA, com pré-visualização circular do avatar
- **Canais por agente**: cada agente tem `channels: {webchat, whatsapp, instagram, telegram}` independentes com tokens próprios (WA: access_token+phone_number_id, IG: access_token+page_id, Telegram: bot_token). Não há partilha global de canais.
- **Widget premium (Intercom/Drift style)**: header gradient azul, avatar circular com indicador de status verde animado, welcome message personalizado, icebreakers em pills clicáveis, cards estruturados com imagem + preço + link, typing indicator animado, footer branded
- **Endpoint público** `/api/public/agent/{tenant_id}?agent_id=...` (sem auth) que devolve identidade para o widget carregar
- **widget.html** movido para ficheiro estático `/app/backend/widget.html` — mais fácil de manter e evita problemas com Python triple-quoted strings
- Correção: sender_name em mensagens AI usa SEMPRE `agent.get("name", ...)` — nunca placeholders tipo "greeting" ou "bot"

### Verificação end-to-end
- [x] `GET /api/public/agent/{tid}` → devolve name, avatar_url, welcome_message, icebreakers, tenant_name
- [x] Widget em `/api/widget/{tid}` carrega identidade dinamicamente e mostra avatar + nome + welcome + icebreakers
- [x] Ao enviar "Quero T3 em Lisboa" no widget → AI responde em PT e devolve card T3 Campo de Ourique com imagem real
- [x] PUT agents guarda `channels.telegram.enabled=true` + bot_token e persiste
- [x] Chatbot test slide-over na UI interna usa mesma identidade

## Backlog P0
- Webhook real Telegram (usando bot_token do agente, não integração global)
- Webhook real WhatsApp Cloud (usando access_token do agente)
- Reconexão automática WebSocket

## Backlog P1
- Upload de avatar (object storage) em vez de URL manual
- Vector embeddings
- CRMs reais via OAuth
- Split `server.py` em routers

## Backlog P2
- Rate limiting
- Multi-agente com routing por tags
- Stripe billing
- SLAs nos tickets
