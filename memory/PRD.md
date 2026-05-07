# Consenso Plus — PRD (v3.6)

## Visão geral
Sistema SaaS multi-tenant PT-PT onde cada negócio cria agentes IA independentes para comunicar com clientes via WhatsApp, Telegram e Webchat. Cada agente é uma unidade completa e isolada (canais, email, fontes, IA, instalação).

**Domínio oficial**: `consenso-agents.com`
**Site comercial**: `consenso-shop.eu`

## v3.6 (2026-02) — Limpeza para produção + agente Maria

### Limpeza para uso real (P0 · concluído)
Script idempotente `cleanup_for_production.py` removeu todos os dados de teste/demo:
- **13 tenants apagados** (TEST_*, TestCo_*, "Imobiliária Lisboa" duplicado, "A minha empresa" do `demo@consenso-agents.com`)
- **Conta `demo@consenso-agents.com` removida** (era placeholder)
- **57 conversas + 220 mensagens + 51 leads + 1 ticket** fictícios apagados do tenant principal
- **Agente "Aria" duplicado** apagado (legado de seed antigo)
- **1 data source órfã + 49 chunks** limpos
- **Tenant principal renomeado**: "Imobiliária Lisboa" → **"Consenso"**

**Mantidos (intencionais)**:
- `admin@consenso-agents.com` / `100%Consenso` (conta principal)
- Agente **Abby** + 9 imóveis reais da ABBI (extraídos de abbimoveis.com)
- `cevlmiguel@gmail.com` (signup real, tenant "Imo")

### Novo agente — Maria (Assistente Consenso) (P0 · concluído)
Script `seed_maria.py` cria/atualiza um agente dedicado ao site comercial `consenso-shop.eu`.

**3 missões ao mesmo nível**:
1. **EXPLICAR** — o que é um agente IA para imobiliárias (multilingue 24/7, qualificação, marcação de visitas)
2. **VENDER** — converter visitantes em pedidos de demonstração (mensalidade fixa, sem fidelização, reembolso até onboarding)
3. **DEMO MODE** — quando o utilizador pede "ver como funciona" ou "testar", a Maria entra em simulação interativa, fingindo ser uma agente de uma imobiliária fictícia (qualifica, apresenta imóveis, marca visita) e no fim regressa ao modo "Maria" com CTA para demonstração personalizada

**Knowledge base**: 11 chunks indexados a partir do scraping do site `consenso-shop.eu` (problemas que resolve, 3 passos de implementação, idiomas, planos, FAQs, contacto).

**Configuração**:
- `welcome_message`: "Olá! 👋 Sou a Maria, assistente da Consenso. Quer ver como um agente IA funciona na prática?"
- 4 icebreakers: "💡 O que é um agente IA?" · "🎬 Quero ver uma demo" · "🏠 Como funciona numa imobiliária?" · "📅 Pedir demonstração"
- Tom: consultivo, profissional, direto · Idioma: PT-PT
- Tools: `create_lead` (captura nome/email/telefone naturalmente)
- Modelo: gemini-2.5-flash via Emergent LLM Key

**Validação curl** dos 3 cenários:
- ✅ Explicar — definição clara: "atende clientes 24/7, em vários idiomas, conhece o portefólio"
- ✅ Vender — refere "mensalidade fixa, sem fidelização" + propõe agendar demonstração
- ✅ Demo Mode — entra em simulação: "Vou simular um atendimento real para veres... [Como agente da Imobiliária Fictícia] Olá! Procura comprar ou arrendar?"

### Estado final do tenant Consenso (admin@consenso-agents.com)
- 2 agentes: **Abby** (cliente ABBI Imóveis) · **Maria** (Consenso — landing page consenso-shop.eu)
- 0 conversas, 0 leads, 0 tickets (limpo, pronto para produção)
- Pronto a embeber Maria via iFrame/Script no `consenso-shop.eu` e Abby no site da ABBI

## v3.5 (2026-02) — Hardening pré-deploy + bug fix dos cards

### Bug fix · Cards a falharem aleatoriamente (P0 · concluído)
**Sintoma reportado**: A Abby às vezes apresentava imóveis "mal" — só aparecia texto e links em vez de cards visuais com imagens.

**Causa raiz** (`/app/backend/ai/orchestrator.py`): quando o LLM ocasionalmente devolve markdown/listas em vez de JSON estrito, `extract_json` falhava → fallback caía em "raw text" sem cards.

**Correções aplicadas**:
1. **One-shot retry** se 1º parse falha
2. **Fallback estruturado** usando metadata do `retrieved[]`
3. **Safety net** auto-anexa cards se reply menciona imóveis
4. Helper `_retrieved_to_cards()`

**Validação** (curl direto ao agente Abby):
- ✅ "T2 em Lagos" → 2 cards com imagens e links
- ✅ "moradia V4 Braga" → 1 card relevante
- ✅ "olá" → 0 cards (correto, não é uma query de imóvel)

### Suite de testes consolidada (P0 · concluído)
- Novo `tests/conftest.py` carrega `REACT_APP_BACKEND_URL` automaticamente do `frontend/.env`
- 3 ficheiros legados v2 marcados com `pytestmark = pytest.mark.skip` (`backend_test.py`, `test_v2_config.py`, `test_webhooks_iter7.py`) — assumiam IDs e schema obsoletos
- Removido fallback de URL preview hardcoded em `test_crm_qualify.py`
- **Resultado**: `30 passed · 0 failed · 42 skipped (legados v2 documentados)`

### Pre-launch verification (10/10)
- [x] Serviços (backend, frontend, mongodb, nginx) RUNNING
- [x] Auth: novos emails 200, antigos 401
- [x] Sweep zero referências a `consenso.plus`/`consensoplus.com`/`business-os-hub`/`preview.emergentagent.com` (excepto testes negativos intencionais)
- [x] Vars protegidas (`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `EMERGENT_LLM_KEY`, `REACT_APP_BACKEND_URL`)
- [x] Widget HTML — CSP `frame-ancestors *`, `X-Frame-Options: ALLOWALL`, CORS ✅
- [x] Widget JS — `application/javascript`, CORS aberto
- [x] Lint frontend `src/`: zero issues
- [x] Pytest backend (suite v3 ativa): **30 passed**
- [x] Smoke test E2E: Login → Painel → Caixa → CRM panel → Agentes/Instalação (3 snippets) — **10/10**
- [x] Cards bug: validado via curl em 3 cenários

## v3.4 (2026-02) — Limpeza global de domínio antigo

### Migração de domínio (P0 · concluído)
- Varredura global feita em todo o codebase (frontend + backend + configs + scripts)
- Removidas/migradas todas as referências aos domínios antigos `consenso.plus` e `consensoplus.com` para `consenso-agents.com`
- **User-Agent backend** (`ai/retrieval.py`): `https://consenso.plus` → `https://consenso-agents.com`
- **Email admin tenant limpo** (`seed.py` + DB): `demo@consenso.plus` → `demo@consenso-agents.com`
- **Email admin tenant ABBI** (`seed_abbi.py`/`seed_demo.py` + DB): `admin@consensoplus.com` → `admin@consenso-agents.com`
- **Migração da BD**: `backend/migrate_emails.py` (idempotente) renomeia utilizadores existentes — executado com sucesso (matched=1/mod=1 em ambos)
- **Testes backend**: emails atualizados em todos os ficheiros sob `backend/tests/`
- **Test credentials**: `/app/memory/test_credentials.md` atualizado com novos emails

### Mantidos (intencional)
- Marca "Consenso+" / "Consenso Plus" — é o nome do produto, não o domínio
- `frontend/.env` `REACT_APP_BACKEND_URL` — variável protegida, sobrescrita pela plataforma no deploy para `https://consenso-agents.com`
- Scripts `assets.emergent.sh` e PostHog em `index.html` — geridos pela plataforma

## v3.3 (2026-05-03) — Webhooks reais + lazy-load Inbox

### Webhooks inbound (P0)
- **Telegram**: `POST /api/webhooks/telegram/{tenant_id}/{agent_id}` — recebe updates, processa via IA com o agente específico, envia resposta via Telegram Bot API usando `bot_token` do próprio agente
- **WhatsApp Cloud**: `GET` para Meta verification (`hub.mode/verify_token/challenge`) + `POST` para receber mensagens; resposta via Graph API v20.0 usando `access_token` + `phone_number_id` do agente
- Novo campo `verify_token` em `channels.whatsapp` (por agente) — configurável na UI (`data-testid="channel-whatsapp-verify_token"`)
- Novo módulo dedicado `/app/backend/webhooks.py` (precursor do refactor completo do server.py)
- URLs visíveis na UI por agente no separador Canais

### Lazy-load de mensagens (P0)
- Backend: `GET /api/conversations/{id}?limit=100&before=<iso>` paginado, com `total` e `has_more`
- Frontend `Caixa.jsx`: carrega últimas 100 mensagens; botão "↑ Carregar anteriores" (`btn-load-more`) no topo; **scroll anchor preservado com precisão absoluta** (`diff=0px`) ao carregar mais

### Verificação (iteration_7 — 10/10 backend + UI validada)
- [x] Telegram webhook: 200 com canal ativo, 400 se desativado, 404 se agente inexistente
- [x] WhatsApp verify: 200 com challenge correto, 403 com token errado
- [x] WhatsApp inbound: payload Meta (entry→changes→value→messages) corretamente extraído
- [x] Conversa aparece em `GET /api/conversations?channel={telegram|whatsapp}` após webhook
- [x] Paginação: página 1 + página 2 (before) + última página com `has_more=false`
- [x] UI: botão "Carregar anteriores" + scroll anchor preservado (diff=0px verificado)
- [x] UI: campo verify_token visível e funcional no WhatsApp

## v3.2 (2026-05-03) — FIX crítico da Inbox (scroll)

### Bugs corrigidos
- Scroll saltava para o topo ao mudar de conversa
- Scroll era "roubado" ao receber mensagem via WebSocket mesmo quando o utilizador estava a ler histórico antigo
- WebSocket reconectava a cada troca de conversa (memory leak potencial)
- Re-render completo da lista de mensagens a cada evento → lag com conversas longas

### Correções
- WebSocket abre **uma só vez** no mount, com auto-reconnect; usa `selectedIdRef` para filtrar eventos
- Mensagens chegadas via WS são **adicionadas incrementalmente** (com dedup por id), não refazem fetch
- Scroll manipulado apenas no `msgsContainerRef` (nunca `scrollIntoView` que movia o viewport pai)
- **Só** auto-scrolla se utilizador estava perto do fundo (`<120px`) OU se foi o próprio a enviar. Caso contrário aparece pill **"Novas mensagens ↓"** (`btn-new-msg-pill`)
- `React.memo` em `ConvoItem`/`MessageRow` + `useMemo` na lista renderizada → zero re-renders desnecessários
- Error state com botão "Tentar novamente" se fetch do thread falhar

### Verificação end-to-end (iteration_6 — 10/10)
- [x] Scroll inicial no fundo numa conversa de 200 mensagens
- [x] Scroll manual para o topo preservado (sem auto-jump após 5s idle)
- [x] Mudar de conversa e voltar → snap to bottom correto
- [x] Enviar mensagem própria → scroll para o fundo
- [x] Mensagem noutra conversa via WS não afeta scroll da atual
- [x] 5 mudanças consecutivas → só 1 WebSocket ativo (zero leak)
- [x] Zero console errors

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
- Reconexão automática WebSocket no widget (atualmente sem retry no widget.html)

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
