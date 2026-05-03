# Consenso Plus — PRD (v3.1)

## Visão geral
Sistema SaaS multi-tenant PT-PT onde cada negócio cria agentes IA independentes para comunicar com clientes via WhatsApp, Telegram e Webchat. Cada agente é uma unidade completa e isolada (canais, email, fontes, IA, instalação).

## v3.1 (2026-05-03) — FIX crítico do widget (script + shortcode)

### Bug corrigido
**Causa raiz**: o snippet de instalação gerava `<script src="${backendUrl}/widget.js">` (sem `/api`). O ingress Kubernetes encaminha tudo sem `/api` para o frontend React, que devolvia `index.html` em vez do ficheiro JS do widget. Por isso o script "carregava" mas nada acontecia no site do cliente.

### Correções aplicadas
- Snippet em `Agentes.jsx` passa a usar `${backendUrl}/api/widget.js`
- Removidas rotas não-prefixadas do backend (`/widget.js`, `/widget/{tid}`) que nunca chegariam ao servidor em produção
- **widget.js reescrito** com: lazy iframe (carrega apenas ao 1º clique), launcher sempre visível com CSS `!important` (z-index 2147483646), resolução de origin cross-domain a partir do script src, fallback visual se iframe falhar em 8s, API pública `window.ConsensoPlus.{open,close}`
- Novo endpoint `GET /api/widget-test/{tenant_id}/{agent_id}` → serve página de demonstração que carrega o script real, permitindo ao utilizador testar exatamente o que o cliente verá
- Novo snippet PHP `functions.php` (alternativa ao plugin WP) no separador Instalação com `data-testid="btn-copy-php"`
- Novo botão "Abrir página de teste" (`btn-test-real-page`) no separador Instalação

### Verificação end-to-end (iteration_5)
- [x] Backend 9/9: /api/widget.js devolve application/javascript com CORS `*`
- [x] /api/widget-test/<tid>/<aid> devolve HTML com tenant/agent IDs
- [x] Playwright: ícone aparece, clicar abre iframe, Aria responde a "Procuro T3 em Lisboa até 500k" com card do Campo de Ourique
- [x] Sem regressões no agent-centric (channels/email persistem, /test-channel e /test-email OK)

## v3.0 (2026-05-03) — Arquitetura 100% AGENT-CENTRIC

### Alterações principais
- **Removida** a página global "Canais & Email" (`/app/canais`) e o link da sidebar. Redirect automático para `/app/agentes`.
- **Canais, Email e Instalação são por-agente** — zero partilha global de tokens ou configuração.
- **Agentes IA** com editor em 7 separadores: Identidade · IA & Instruções · Canais · Email · Instalação · Fontes & Ferramentas · Pré-visualizar.
- **Canais suportados (por agente)**: Web Chat, WhatsApp, Telegram (Instagram/Messenger removidos do produto).
- **Email SMTP por agente** (`agent.email` dict): host, port, secure, username, password, from_email, notify_email, enabled.
- **Notificações automáticas de leads** agora usam a config SMTP do agente que processou a conversa (não mais global).
- **Instalação do widget** gera automaticamente:
  - Script HTML: `<script src=".../widget.js" data-tenant-id="..." data-agent-id="..." defer></script>`
  - Shortcode WordPress: `[consenso_chat agent_id="..."]`
  - Pré-visualização ao vivo via iframe
  - Passos claros de instalação (colar antes de `</body>`)
- **Teste de canais em tempo real**:
  - `POST /api/agents/{id}/test-channel/telegram` → valida via `getMe` da Telegram Bot API
  - `POST /api/agents/{id}/test-channel/whatsapp` → valida via Graph API v20.0 (WhatsApp Cloud)
  - `POST /api/agents/{id}/test-channel/webchat` → confirma widget pronto
- **Teste de email**: `POST /api/agents/{id}/test-email` envia email real via SMTP do agente.
- **Webchat multi-agente**: `POST /api/webchat/{tenant_id}/message` aceita `agent_id` opcional → cada widget instalado usa o agente específico.
- **Widget.js / widget.html** passam `data-agent-id` pelo iframe até ao backend.
- **Registo de novo tenant** já não cria integração global "webchat"; em vez disso o agente inicial tem `channels.webchat.enabled=true`.

### Verificação end-to-end (iteration_4)
- [x] Backend pytest 10/10: canais (webchat/telegram/whatsapp), email, webchat com agent_id, registo sem global webchat
- [x] Frontend: sidebar sem "Canais & Email", 7 separadores, 3 canais, preview com icebreakers clicáveis
- [x] Persistência: `channels`, `email` guardados em `PUT /api/agents/{id}`
- [x] Copy buttons em script, shortcode e webhook URLs

## Credenciais
- Email: `demo@consenso.plus` / Senha: `demo1234` (ver `/app/memory/test_credentials.md`)

## Backlog P0
- Webhook real Telegram/WhatsApp inbound (endpoints `/api/webhooks/{telegram,whatsapp}/{tenant_id}/{agent_id}`) — UI já mostra as URLs
- Reconexão automática WebSocket no widget

## Backlog P1
- Upload de avatar (object storage) em vez de URL manual
- Vector embeddings (atualmente retrieval por palavras-chave)
- Plugin oficial WordPress para interpretar o shortcode
- Refactor `server.py` (1016 linhas) em `routers/{auth,agents,channels,data_sources,conversations,leads,tickets,team,widget}.py`
- Extrair tabs de `Agentes.jsx` (790 linhas) para `pages/agentes/tabs/`

## Backlog P2
- Rate limiting
- Multi-agente com routing por tags dentro do mesmo tenant
- Stripe billing
- SLAs nos tickets
- Analytics avançadas
- CRMs via OAuth (HubSpot, Pipedrive, Salesforce) — atualmente removidos da UI
