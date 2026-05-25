# Consenso Plus — PRD (v3.19)

## Visão geral
Sistema SaaS multi-tenant PT-PT onde cada negócio cria agentes IA independentes para comunicar com clientes via **WhatsApp, Telegram, Instagram Direct e Facebook Messenger**, além de Webchat com **streaming token-a-token** e **cards imobiliários premium**. Cada agente é uma unidade completa e isolada (canais, email, fontes, IA, instalação).

**Domínio oficial**: `consenso-agents.com`
**Site comercial**: `consenso-shop.eu`

## v3.21 (2026-02/05) — Verificação Final + Tema Unificado + Novo Agente ImmoAI

### Tema CONSENSO unificado em TODOS os agentes
- Novo módulo **`/app/backend/brand.py`** — `CONSENSO_THEME` (primary `#4591CE`, primary_dark `#2C6FA8`, primary_soft `#E8F1F9`, primary_border `#C7DDF0`, bot `#E4AC1E`).
- `seed_maria.py`, `seed_staylocal.py`, `seed_tejo_sailing.py`, `seed_immoai.py` e `bootstrap.py` (Abby) agora importam de `brand.CONSENSO_THEME` — fonte única de verdade.
- Os 5 agentes seedados partilham agora identidade visual base; clientes podem ainda customizar cada agente via dashboard (tab "Visual & Cores") com ajustes de contraste/acessibilidade.

### Reforço conversacional (Maria + todos os agentes)
- `ai/global_rules.py` regra #2 alargada: interpretação inteligente de respostas curtas ("eu"/"1"/"um" = 1 utilizador, "nós" = 2-5, "sim/ok/claro" = confirmação positiva, frases incompletas = inferir contexto e avançar).
- Regra #4 alargada: ZERO loops, NUNCA reiniciar fluxos, NUNCA pedir clarificação sobre input parcial — escolher a interpretação mais provável e avançar.
- `ai/memory.py` `_USER_QUESTION_KEYWORDS` expandido (cobre "sois quantos", "trabalhas sozinho", "elementos da equipa", etc.) para capturar todas as variações naturais quando o agente perguntou sobre dimensão da equipa.

### Novo agente: ImmoAI — Consultor Imobiliário Digital
- **`/app/backend/seed_immoai.py`** (novo) — agente human-like que simula um consultor imobiliário experiente.
- 5 imóveis demo: T2 Benfica €285k · T3 Parque Nações €520k · T4 Cascais €950k · T1 Porto €210k · T3 Almada €330k.
- 6 icebreakers ("Estou à procura de casa", "Quero vender", "Que imóveis tens?", "Agendar visita", "Boas opções em Lisboa", "Falar com consultor").
- SYSTEM_PROMPT define expressões humanas obrigatórias ("Perfeito 😊", "Boa", "Excelente escolha") e proíbe frases robóticas ("Como assistente virtual", "Sou um chatbot").
- Fluxo conversacional comprar/vender/visita com filtro de orçamento (validação real: pedido "T2/T3 até 350k" → exclui corretamente €520k e €950k, mostra Benfica €285k + Almada €330k).
- Suporte completo a `reset-defaults` e à flag `is_customized`.

### Outras melhorias
- `AgentInput.notify_email` e `AgentInput.email` agora `Optional` — permite clientes fazer PUT com payload de GET sem coercion manual.

### Validação
- ✅ **Backend testing agent**: 14/14 novos testes passaram + 37/37 regressões (51/51 total) · 0 failures.
- ✅ Validação end-to-end: ImmoAI guia o utilizador desde "estou à procura de casa" até "marca-me visita ao primeiro" em 5 turnos, com cards filtrados, tom humano e CTA em cada resposta.
- ✅ Maria: "Olá quanto custa?" → "eu" → STARTER recomendado sem repetir perguntas; "sim" → link de demo partilhado naturalmente.


## v3.20 (2026-02) — Regras Globais CONSENSO PLUS + Customização Total no editor de Agentes

### Implementado
**Backend — Regras globais (`/app/backend/ai/global_rules.py`)**
- Novo módulo central com 10 regras CONSENSO PLUS aplicadas a TODOS os agentes (Maria, StayLocal, Tejo, Abby, e agentes criados pelo cliente).
- Regras: tom PT-PT informal "tu" (nunca pt-BR), 1 mensagem por turno, sem repetir perguntas, interpretação inteligente de respostas curtas ("eu"=1 user), layout fixo de PLANOS em Markdown, 1 pergunta por turno, idioma dinâmico, follow_up vazio por defeito.
- `orchestrator.py` injeta o bloco no `system` prompt acima do prompt específico do agente, tanto em `generate_response` como em `generate_response_stream`.

**Backend — Filtro `follow_up` reforçado**
- Expandida a lista `_BAD_GENERIC_FOLLOWUPS` (cobre "estou aqui para ajudar", "fico a aguardar", "qualquer dúvida", etc.).
- Threshold de paráfrase reduzido de 65% → 55%.
- Nova helper `_reply_already_has_cta`: se reply já tem `?` ou link, follow_up sem valor é cortado.
- Follow-ups < 8 caracteres são descartados.
- Mantida exceção: follow_up COM valor (link, contacto, "@") é sempre aceite — alinhado com a regra do utilizador "manter, mas só em casos específicos".

**Backend — Customização persistente (resistente ao bootstrap)**
- Modelos `Agent` e `AgentInput` (`models.py`) ganharam dois campos: `theme: Dict` e `is_customized: bool`.
- `PUT /api/agents/{id}` marca automaticamente `is_customized=true` em cada update.
- Novo endpoint **`POST /api/agents/{id}/reset-defaults`** repõe `system_prompt`+`icebreakers`+`welcome`+`theme`+`knowledge` para a versão oficial do seed e remove a flag.
- **`bootstrap.py` agora respeita `is_customized`**: se `true`, NÃO sobrescreve campos de conteúdo no startup (preserva customizações do dashboard). Aplica-se tanto a `_ensure_agent_with_kb` como a `_ensure_abby`.
- Inserts iniciais incluem `is_customized: False` para contrato consistente.

**Frontend (`/app/frontend/src/pages/Agentes.jsx`)**
- Nova tab **"Visual & Cores"** com 5 color pickers (primary, primary_dark, primary_soft, primary_border, bot) — duplo input (`<input type="color">` + hexcode editável) e descrição contextual de cada cor.
- **Pré-visualização ao vivo** do widget com as cores aplicadas (header gradiente, icebreakers, bolhas bot/user com preço em destaque, botão enviar).
- Botão **"Repor cores"** repõe o tema CONSENSO Plus (azul `#4591CE` + dourado `#E4AC1E`).
- Tab "IA & Instruções" reorganizada: prompt do sistema com 10 linhas + nota "regras globais Consenso Plus são aplicadas por cima destas".
- Novo painel **"Repor predefinições do seed"** no fim da tab AI — botão que chama `POST /agents/{id}/reset-defaults`, badge "Modo Customizado" visível quando `is_customized=true`.

### Validação
- ✅ **Backend testing agent**: 12/12 testes novos (`test_iter14_global_rules.py`) — 0 regressões nos 25 testes anteriores.
- ✅ Maria respeita layout fixo de planos: "Olá, quanto custa?" → 1 mensagem com STARTER/PRO/ENTERPRISE em bullets + pergunta de qualificação, `follow_up=None`.
- ✅ Anti-loop: "eu" → não repete perguntas nem usa "desculpa pela confusão".
- ✅ Sector hotelaria: pergunta sobre hotel NÃO mostra property cards.
- ✅ Multi-idioma: "Hello..." → resposta em EN, `language=en`, sem pt-BR.
- ✅ Persistência customização: PUT → restart backend → cores e welcome customizados **preservados**.
- ✅ Reset funcional: `POST /reset-defaults` volta às predefinições do seed.
- ✅ Smoke test visual: tab "Visual & Cores" renderiza corretamente com pré-visualização ao vivo.


## v3.19.3 (2026-02) — Pre-deploy hardening de TODOS os 4 agentes

### Mudanças
**`_ensure_abby` tornou-se idempotente** (era a única função que só criava, nunca atualizava):
- Agora faz upsert do `name`, `welcome_message` e `icebreakers` em cada deploy
- Corrigido nome em DB: "Abby — ABB Imóveis" (typo antigo) → "Abby — ABBI Imóveis"
- Welcome message adicionado: "Olá! 👋 Sou a Abby da ABBI Imóveis..."
- Icebreakers: 🏠 Comprar/simular · 🔑 Arrendar · 📈 Investimento · 📑 Documentos

**Single source of truth para nomes dos agentes**:
- Bootstrap agora importa `AGENT_NAME as SL_NAME` (StayLocal) e `AGENT_NAME as TJ_NAME` (Tejo Sailing) em vez de strings hardcoded
- Garante que mudar o nome em qualquer `seed_*.py` propaga automaticamente em produção no próximo bootstrap

### Estado em DB após bootstrap (tenant Consenso):
```
Abby — ABBI Imóveis                        | ice=4 | welcome=Olá! 👋 Sou a Abby da ABBI Imóveis...
Maria — Assistente IA Consenso Plus        | ice=5 | welcome=Olá! 👋 Sou a Maria, a assistente IA da Consenso Plus...
StayLocal Concierge AI                     | ice=3 | welcome=Bem-vindo ao StayLocal · Welcome 🌿 Sou o teu concierge...
Tejo Sunset Sailing AI Guide               | ice=6 | welcome=Olá ⛵️ Sou o Tejo Sailing AI...
```

### Validação final
- ✅ **Deployment Agent: PASS** — zero blockers, todos os checks passam
- ✅ **63/63 pytest passed** — zero regressões
- ✅ Backend imports OK, syntax limpo em todos os ficheiros Python
- ✅ Schedulers em background a correr (follow-up + property feed)
- ✅ Logs claros: `[bootstrap] refreshed agent 'NAME' prompt_len=N ice=N kb_chunks=N`
- ✅ Single source of truth: AGENT_NAME constants em seed_maria.py, seed_staylocal.py, seed_tejo_sailing.py
- ✅ Idempotência total: 4/4 agentes refrescados em cada startup sem duplicar nada

## v3.19.2 (2026-02) — Icebreakers focados em ROI + StayLocal uniformizado

### Maria — novos icebreakers ROI-driven
3 novos icebreakers de alto valor comercial:
- 📈 "Qual é o ROI esperado?"
- ⏰ "Como evitar perder pedidos fora de horas?"
- 🤖 "Como reduzir trabalho no atendimento?"
+ 💰 "Ver planos e preços" e 🎬 "Marcar uma demo"

### StayLocal Concierge AI — tom uniformizado para "tu"
**Bug**: StayLocal misturava "sinta-se / aproveite a sua / recebê-lo" (formal pt-BR).
**Fix**: System prompt e welcome reescritos com "tu/teu/contigo". Bloco IDIOMA E TOM agora bane explicitamente "você/sua/seu/sinta-se/aproveite a sua/o senhor/pretende/poderia". Tom premium pela escolha de palavras, não pela formalidade arcaica. Adicionado bloco "5) HOSPEDADO" para responder a hóspedes presentes (WiFi, check-in, recomendações locais).

### Testes E2E realizados
**Maria** (5 cenários):
- ✅ "Qual é o ROI esperado?" → resposta consultiva com números
- ✅ "Como evitar perder pedidos fora de horas?" → fala de 24/7 + multicanal
- ✅ "Como reduzir trabalho no atendimento?" → automação + qualificação
- ✅ "Ver planos e preços" → bullets perfeitos
- ✅ Reposicionamento multissetorial mantido

**StayLocal** (4 cenários):
- ✅ "Sou hóspede e cheguei agora" → "ajudar-te na tua estadia" (tom tu)
- ✅ "Qual a password do WiFi?" → "confirmar isso para ti"
- ✅ "reserva romântica em Lisboa" → "tua estadia romântica"
- ✅ "Hello! romantic stay in Porto" → resposta inteira em EN
- ✅ "Hola! hotel romántico" → resposta inteira em ES

**Regressões**: 63/63 pytest passed

## v3.19.1 (2026-02) — Hotfix: bootstrap não estava a atualizar o nome da Maria

### Bug
Após o redeploy da v3.19, a Maria continuava em produção com o nome antigo "Maria — Consenso SDR AI" porque `bootstrap.py` tinha o nome **hardcoded** em vez de importar do `seed_maria.py`.

### Fix
- `bootstrap.py` agora importa `AGENT_NAME as MARIA_NAME` do `seed_maria.py` (single source of truth)
- O role/goal do agente também foram atualizados para refletir o posicionamento multissetorial
- Log enriquecido com `prompt_len` para confirmar visualmente que cada agente foi refrescado em cada startup

### Validação
- Local: agente Maria agora persiste com nome correto `"Maria — Assistente IA Consenso Plus"` após bootstrap
- Logs: `[bootstrap] refreshed agent 'Maria — Assistente IA Consenso Plus' (4b4dbf03…) prompt_len=12474 ice=6 kb_chunks=26`

## v3.19 (2026-02) — Maria como Assistente IA global da plataforma Consenso Plus

### Reposicionamento estratégico
A Maria deixa de ser "consultora SDR imobiliária" e passa a ser **Assistente IA principal da CONSENSO PLUS**, com 4 áreas oficiais reconhecidas explicitamente:
- 🏠 **Imobiliário**
- 🛎️ **Hotelaria**
- 🌍 **Turismo**
- 💼 **Empresas de Serviços** (consolida clínicas, restauração, e-commerce, consultoria, atendimento corporativo)

### Mudanças implementadas
1. **System prompt re-escrito** (`seed_maria.py`):
   - Identidade: "Assistente IA principal da CONSENSO PLUS"
   - 4 áreas oficiais com hints de deteção por palavras-chave
   - Setores adjacentes mapeados para "Empresas de Serviços"
   - Imobiliário tratado como UMA das 4 áreas (não como default)
   - Bloco "MODO IMOBILIÁRIO PREMIUM" condicional — só ativa com sinais explícitos

2. **Welcome message neutro**: "Olá! 👋 Sou a Maria, a assistente IA da Consenso Plus. Posso ajudar-te a explorar a nossa plataforma. Em que área queres focar — Imobiliário, Hotelaria, Turismo ou Empresas de Serviços?"

3. **Icebreakers atualizados** — 4 áreas + planos + demo:
   - 🏠 Imobiliário · 🛎️ Hotelaria · 🌍 Turismo · 💼 Empresas de Serviços · 💰 Ver planos · 🎬 Marcar demo

4. **Nome do agente**: "Maria — Consenso SDR AI" → "Maria — Assistente IA Consenso Plus"

5. **`page_context` (novo, preparado para website futuro)** — campo opcional na `InboundMessage`:
   - Widget aceita `?context=hotelaria` (ou `imobiliario`/`turismo`/`servicos`/`geral`) na URL e propaga no payload
   - Backend mapeia em `ai/page_ctx.py` → injeta bloco `CONTEXTO DA PÁGINA:` no system prompt
   - Maria arranca já focada na área certa quando o website Consenso Plus estiver pronto

### Validação E2E
- ✅ **Homepage neutra**: "Como posso ajudar-te hoje?" — zero suposições
- ✅ **`page_context=hotelaria`**: foca em reservas, WhatsApp, suporte (sem imóveis)
- ✅ **`page_context=turismo`**: lista as 4 áreas oficiais para confirmar
- ✅ **Visitante imobiliária explícita**: apresenta planos com bullets, sem cards de imóveis (não pediu)
- ✅ **"mostra-me imóveis em Lisboa"**: 3 cards (intenção explícita)
- ✅ **63/63 pytest passed**, zero regressões

## v3.18 (2026-02) — Memória contextual + tom uniformizado + renderização de planos

### Bugs corrigidos
1. **Memória zero** — Maria repetia a mesma pergunta "Com quantos utilizadores pretendes iniciar?" mesmo depois do utilizador responder "EU", "1", "só eu". Resolvido com novo módulo `/app/backend/ai/memory.py` que extrai factos persistentes (nº utilizadores, setor, nome, email, telefone) do histórico e os injeta no system prompt como bloco "JÁ SABEMOS DO UTILIZADOR". O LLM é instruído explicitamente a NUNCA voltar a perguntar info já recolhida.
2. **Tom misturado** — banido "você/sua/pretende/poderia/o senhor". Reforçado uso obrigatório de "tu/teu/contigo" no system prompt (4 reforços em locais críticos).
3. **Planos com `\•` literal** — system prompt agora obriga uso de quebras de linha reais com bullets reais. Widget renderiza markdown leve (`formatBotText`) que limpa o glitch `\•` automaticamente, converte `\n` em `<br>`, faz auto-link de URLs e suporta `**bold**`.
4. **Imóveis sem contexto** — regra explícita: "SÓ apresenta cards se houver intenção imobiliária explícita. NUNCA em conversas sobre planos, demos, hotelaria, clínicas."
5. **Mensagens duplas redundantes** — system prompt reforça `follow_up: ""` sempre que possível. Anti-redundância em `_filter_redundant_followup()` já em vigor desde v3.17.
6. **Agendamento direto** — Maria partilha `https://consenso-shop.eu/marcar-reuniao` imediatamente quando há interesse comercial, sem pedir email/nome antes ("o link trata disso").

### Implementação
- **Novo**: `/app/backend/ai/memory.py` (160 linhas, sem LLM) — `collect_facts()` + `format_facts_pt()`
- **Atualizado**: `ai/orchestrator.py` — injeta `facts_block` no prompt do endpoint clássico **E** do streaming SSE
- **Atualizado**: `widget.html` — função `formatBotText()` renderiza bullets, quebras de linha, links e remove o `\•` glitch
- **Atualizado**: system prompts (classic + stream) com 8 instruções críticas concisas

### Validação
- ✅ **63/63 pytest passed** (phase1 + webchat_stream + widget + meta_channels + health_dashboard)
- ✅ **Memória 4/4 cenários OK**: "só eu" → 1, "EU" → 1, "1" → 1, nome+email+setor numa frase → todos extraídos
- ✅ **E2E**: Maria não repete pergunta dos utilizadores após "EU/só eu", partilha link de agendamento spontaneamente, planos renderizam com bullets perfeitos
- ✅ **Tom**: "agendares/teu/contigo" em todos os outputs testados, zero "você/pretende"
- ✅ Botão dourado + launcher dourado funcionais

## v3.17 (2026-02) — Maria multissetorial + cores Consenso + demos públicas

### 1. Maria expandida para todos os setores
- **Mantém** todo o conhecimento e capacidades imobiliárias (portefólio, visitas, simulação crédito).
- **Adiciona** detecção de contexto setorial: hotelaria, alojamento local, turismo, clínicas, restauração, e-commerce, serviços B2B, consultoria, atendimento corporativo.
- Maria identifica o setor pela conversa e adapta os casos de uso (não assume mais imobiliário).
- 9 novos chunks KB com casos de uso por setor + chunk dedicado ao link de agendamento.

### 2. Cores Consenso aplicadas
- Botão enviar do widget: **#E4AC1E (dourado)** com hover #C7951A e box-shadow dourado.
- Launcher bubble (widget.js): **#E4AC1E (dourado)** com sombra dourada.
- Variáveis CSS introduzidas: `--gold`, `--gold-dark`, `--gold-soft`.
- Mantém azul `#0069FE/#4591CE` em headers, bubbles do utilizador e cards.

### 3. Link de agendamento integrado
- `https://consenso-shop.eu/marcar-reuniao` partilhado naturalmente pela Maria quando há interesse comercial real (demo, reunião, "como avançamos").
- Header das páginas demo também tem CTA dourado "Marcar reunião".

### 4. Anti-redundância de mensagens
Nova função `_filter_redundant_followup()` em `ai/orchestrator.py`:
- Corta follow_ups genéricos sem valor ("Queres saber mais?", "Posso ajudar com mais alguma coisa?").
- Corta follow_ups que parafraseiam o reply (overlap >65%).
- Corta segunda pergunta quando reply já termina em "?" e follow_up não acrescenta link/contacto.
- Aplica-se ao endpoint clássico **E** ao streaming SSE.

### 5. Páginas demo públicas (sem login)
3 landing pages em `/app/frontend/src/pages/Demos.jsx`:
- `/demo` ou `/demo/generalista` → Maria multissetorial (azul Consenso)
- `/demo/hotelaria` → StayLocal Concierge AI (cor dourada)
- `/demo/turismo` → Tejo Sunset Sailing AI Guide (azul-claro)

Cada landing tem hero adaptado ao setor + 4 bullets de benefícios + sample queries + iframe do widget + footer com certificações ISO.

### Validação
- ✅ **114/114 pytest passed** (zero regressões)
- ✅ Manual curl: Maria adapta a hotelaria, clínicas, e fala spontaneamente sobre Consenso quando vago (sem assumir imobiliário)
- ✅ Maria partilha o link de agendamento naturalmente quando pedida reunião
- ✅ Anti-redundância: 5/5 cenários testados (genérico, paráfrase, Q+Q, link, válido)
- ✅ Frontend lint: zero issues
- ✅ Screenshots: demos Hotelaria + Generalista renderizam corretamente com botão dourado

## v3.16 (2026-02) — Simulação de crédito conversacional + comparação lado-a-lado

### Refinamentos sobre v3.15
- 🧮 **Recolha conversacional de dados de crédito**: Maria pede em ordem natural (1 pergunta por turno) montante → entrada → prazo → idade. Detecção de continuação de fluxo (mesmo sem palavras-chave de crédito na resposta).
- 🏦 **Limite bancário pela idade aplicado automaticamente**: regra `80 - idade` calcula prazo máximo permitido pelo banco (ex: 60 anos → max 20 anos). Card mostra "(máx N)" quando há restrição.
- 📊 **Comparação 2 cenários lado-a-lado** no mesmo card: cenário primário (o pedido) + alternativa (prazo ±5 anos). Mostra **delta colorido** (verde se poupa juros, vermelho se paga mais) para ajudar a decisão.
- 🌐 **Regex robusta** para extração de params (`entrada de 30%`, `prazo de 25 anos`, `tenho 45 anos`, `idade 35`, `50 anos de idade`) — distingue corretamente prazo de idade na mesma frase.
- 📋 **Maria apresenta TODOS os planos** numa só mensagem quando perguntado sobre preços (sem fragmentar nem esperar follow-up).
- 🎨 Widget renderiza card de comparação com bloco dedicado `.finance-compare` com grid + diffs coloridos.

### Validação
- ✅ **114/114 pytest passed**: 28 testes Phase 1 (Finance + Lead Score + Property Feed + Comparação cenários) + 86 anteriores. Zero regressões.
- ✅ Deploy Agent: PASS — zero issues bloqueadores
- ✅ Curl E2E: fluxo crédito multi-turno funciona (Turn 1 mostra preliminar, Turn 2+ refina com dados novos)
- ✅ Multi-idioma: 5/5 idiomas (EN/FR/DE/ES/NL) testados

## v3.15 (2026-02) — Phase 1 features (planos Consenso Shop alinhados + features pendentes)

### 1. Maria · Knowledge dos planos Consenso (P0 · concluído)
SYSTEM_PROMPT e KB atualizados em `seed_maria.py` com:
- **STARTER €49,90/mês**: até 2 utilizadores, 2.000 msg/mês, Webchat+WhatsApp, sem CRM/multicanal
- **PRO €74,90/mês** (Mais Popular): 5 utilizadores, ilimitadas, 5 canais, CRM + Lead Scoring + Live Chat Takeover + Integração imóveis terceiros
- **ENTERPRISE sob consulta**: ilimitado + Simulações Financeiras + Follow-up Auto WhatsApp + Otimização Multilingue Website + SLA + Gestor de Conta
Maria recomenda o plano certo conforme o perfil do cliente (testar/escalar/grupo).

### 2. Multi-idioma automático (P0 · concluído)
Reforço no system prompt de `orchestrator.py` (generate_response + generate_response_stream): instruções explícitas para detetar idioma da última mensagem do utilizador e responder EXCLUSIVAMENTE nesse idioma.
- Validado: **5/5 idiomas** (EN, FR, DE, ES, NL) respondem corretamente. PT-PT continua default.

### 3. Simulações financeiras (P0 · concluído)
Novo módulo `/app/backend/ai/finance.py`:
- `calcular_prestacao(valor, entrada_pct, prazo, euribor, spread)` → fórmula PMT
- `detect_finance_intent(text)` → regex PT/EN para "prestação/credito/mortgage"
- `extract_price_from_text(text)` → suporta `500k`, `1.5M`, `350 000€`, `780000€`, `1.450.000 €`
- Hook em `_process_inbound`: detetada intenção + preço → backend calcula prestação e injeta como `kind=knowledge` chunk + gera `card finance_simulation` no widget. Maria comenta o resultado em 1 frase.
- Widget renderiza card especial com prestação destacada (azul brand) + entrada/montante/prazo/taxa em grid.

### 4. Lead Scoring 0-100 automático (P0 · concluído)
Novo módulo `/app/backend/ai/lead_score.py`:
- Algoritmo determinístico (sem LLM) baseado em sinais explícitos:
  - Dados pessoais (até 30 pts): nome, email, telefone
  - Especificidade procura (até 30 pts): tipologia, zona, orçamento
  - Comportamentais (até 30 pts): engajamento, urgência, visita marcada, sim crédito
  - Perfil (até 10 pts): investidor, habitação própria, precisa de crédito
- Tier: **frio** (0-39), **morno** (40-69), **quente** (70-100)
- `_recompute_lead_score()` corre após cada `create_lead` em background
- Visit booking via `/book-visit` cria lead com score=85 tier=quente
- Frontend `Leads.jsx` mostra score com cor (vermelho/laranja/cinza), ícone (🔥🌡️❄️) e sinais no tooltip

### 5. Notificação email ao agente (P0 · concluído)
Hook reforçado em `_notify_new_lead`: subject inclui tier_icon + score (`🔥 Novo lead · Pedro (85)`). Endpoint `/book-visit` também dispara notificação. SMTP per-agent em `agent.email_config` (já existia, agora utilizado).

### 6. Follow-up automático WhatsApp (P0 · concluído)
Novo módulo `/app/backend/follow_up.py` + scheduler em background:
- Cadência: **24h → 72h → 168h** (3 toques) após criação de lead
- Critérios: tem telefone, score >= 40 (morno/quente), agente com WhatsApp ativo, `follow_up_enabled !== false`
- Templates PT/EN inteligentes adaptados a cada step
- Marca `followup_steps: ["fu1", "fu2", "fu3"]` no lead para não duplicar
- Tick a cada 10 min em produção, mas desativável via `DISABLE_SCHEDULERS=1`
- Endpoint manual: `POST /api/agents/follow-up/tick` (admin only)

### 7. Feeds de imóveis externos · Idealista/Imovirtual (P0 · concluído)
Novo módulo `/app/backend/property_feed.py`:
- Parsers: **CSV** (colunas PT ou EN), **XML** (Idealista/Imovirtual style), **Google Sheets** (publicado em CSV)
- Indexa como `kind=external_item` chunks em MongoDB
- Refresh semanal automático em background (scheduler 7 dias)
- Retrieval atualizada (`/app/backend/ai/retrieval.py`): prioriza `kind=item` (carteira própria) > `knowledge` > `external_item`. Só apresenta externos quando o portefólio próprio tem < 2 hits.
- Widget marca cards externos com badge "Parceiro" (amarelo brand)
- Endpoints CRUD: `GET/PUT /api/agents/{id}/feeds`, `POST /api/agents/{id}/feeds/refresh`

### Frontend
- Novo separador **"Automação"** no editor de agentes (`/app/agentes`)
- Componente `AgentAutomation.jsx` com: toggle Follow-up + tabela de feeds (add/edit/remove/refresh)
- Stats por feed: nº de imóveis indexados + último refresh
- `Leads.jsx` com novo display de score (cor/ícone/sinais)

### Validação
- ✅ **85/85 pytest passed** (15 novos em `test_phase1_features.py` + 70 anteriores). Zero regressões.
- ✅ Testing agent v3_fork (iteration_13): 100% backend (34/34 phase1 tests + 104 regression), 100% frontend (Automation tab + panel + feed CRUD + persistence + refresh + Leads tier display)
- ✅ Manual curl: Maria responde em PT/EN/FR/DE/ES/NL corretamente, sabe os 3 planos, faz simulação financeira, book-visit cria lead quente
- ✅ Schedulers arrancam no startup (logs confirmados)

## v3.14 (2026-02) — Maria modo Imobiliária Premium (efeito WOW)

### Demo imobiliário premium (P0 · concluído)
Quando o visitante de `consenso-shop.eu` pergunta por imóveis, casas, apartamentos, T2/V3, Lisboa/Cascais, etc., a Maria responde **imediatamente** com 3 cards visuais premium estilo Sotheby's/Idealista.

**6 propriedades demo curadas** (`seed_maria.py::DEMO_PROPERTIES`):
| Tipo | Título | Zona | Preço | Tipologia |
|---|---|---|---|---|
| Penthouse | Penthouse Tejo View | Príncipe Real | 1.450.000 € | T3 |
| Apartamento | Apartamento Premium Av. Liberdade | Lisboa | 780.000 € | T2 |
| Moradia | Cascais Bay | Quinta da Marinha | 2.890.000 € | V5 |
| Loft | LX Factory | Alcântara | 525.000 € | T1+1 |
| Quinta | Histórica Sintra | Colares | 3.250.000 € | V8 |
| Apartamento | Marina Vilamoura | Algarve | 695.000 € | T2 |

Cada propriedade tem: imagem 200px premium (Unsplash), preço destacado, badge tipologia (`var(--bot)` = amarelo Consenso), localização com 📍, área m², descrição 2 linhas, **4 features pills**, CTA "Ver detalhes →".

**System prompt** atualizado com secção `🌟 MODO IMOBILIÁRIA PREMIUM` — bullet point obrigatório: ao detectar QUALQUER termo imobiliário (15+ keywords incluindo zonas PT), preencher `use_items: [1,2,3]` na primeira mensagem e manter o tom de consultora premium tipo Sotheby's.

**Card UI upgrade**:
- Imagem **200px** (era 160px) com hover scale 1.06 + transition cubic-bezier
- Badge tipologia top-right (background `--bot`, uppercase, shadow)
- Localização + área m² inline com 📍
- **Features pills** (T2 · 110m² · 4 highlights) — design tipo Idealista
- Sombra premium 0 4px 16px → 0 14px 30px no hover
- Card 320px (era 300px) · gap 280px no carrossel

**Backend** — `_retrieved_to_cards()` agora inclui campos opcionais `location`, `typology`, `area_m2`, `features` (lista) quando presentes no `meta`.

**Search keywords** expandidos: cada propriedade tem singular+plural+sinónimos para retrieve robusto (apartamento/apartamentos, moradia/moradias, T1-T5, V1-V5, ver/mostra/há/tens, zonas).

### Validação
| Query | Cards retornados | Match |
|---|---|---|
| "Mostra-me imóveis" | 3 | ✅ |
| "apartamentos em Lisboa" | 3 | ✅ |
| "Tens moradias?" | 3 | ✅ |
| "T2 em Cascais" | 1 | ✅ |
| "Quero comprar casa" | 2 | ✅ |
| "Penthouse" | 1 | ✅ |

DOM check: 3 cards renderizados, primeiro com `img=1 typology-badge=1 price-tag=1 location=1 feature-pills=4`.

### Bootstrap idempotente — demo properties incluídas
`bootstrap.py::_ensure_agent_with_kb` agora aceita `demo_items` opcional → insere como `kind=item` chunks. No próximo deploy, a produção recebe automaticamente as 6 propriedades premium da Maria. Os outros agentes (Abby, StayLocal, Tejo) não são afetados.

## v3.13 (2026-02) — Bootstrap content-upsert (hotfix Maria SDR em produção)

## v3.13 (2026-02) — Bootstrap content-upsert (hotfix Maria SDR em produção)

### Bug · Maria não atualizou em produção após deploy v3.12 (P0 · concluído)
**Sintoma**: O utilizador fez deploy mas a Maria continuou com o nome antigo ("Maria — Assistente Consenso"), prompt antigo e tema antigo (azul `#0069FE` em vez de `#4591CE`).

**Causa raiz**: `bootstrap.py::_ensure_agent_with_kb()` tinha lógica `if existing: return` — protegia agentes editados pelo utilizador mas também impedia atualizações de **conteúdo seedado** entre deploys. Como a Maria já existia no DB de produção, o bootstrap saltava-a sempre.

**Fix** (`bootstrap.py::_ensure_agent_with_kb`):
- **Upsert em cada deploy** dos campos de conteúdo: `name`, `system_prompt`, `knowledge`, `theme`, `avatar_url`, `welcome_message`, `icebreakers`, `role`, `goal`, `default_language`, `api_provider`, `model_*`, `data_source_ids`, `updated_at`
- **Preserva campos editados pelo utilizador**: `channels` (tokens, verify_token), `api_key`, `tools`, `email_config`, `tone`, `rules`, `config`, `created_at`
- **Wipe + re-index do KB** do data_source ligado (chunks são fonte de verdade do `seed_*.py`)
- Nome bootstrap atualizado: "Maria — Assistente Consenso" → "Maria — Consenso SDR AI"
- Role/goal sincronizados com o novo posicionamento SDR

**Validação local** (simulando state de produção):
1. ✅ Forço Maria para state antigo (name + prompt + tema antigos)
2. ✅ Corro `await bootstrap(db)`
3. ✅ Maria volta a SDR AI: prompt SDR completo, tema `#4591CE`, welcome novo, 6 icebreakers

### DB hygiene
- Limpos 13 tenants `TestCo_*` (resíduo de runs do testing agent) + 1 agent órfão
- DB final: 2 tenants (Consenso + Imo), 4 agentes de produção, todos `api_provider=openai`

### Validação final
- ✅ **70/70 pytest passed**
- ✅ TTFT Maria (cold): **0.68s** com 8 chunks
- ✅ Bootstrap idempotente testado em DB simulado prod

### Como funciona o deploy daqui em diante
1. Quando faz `Deploy`, o `bootstrap.py` corre no startup do backend de produção
2. Detecta Maria existente → faz upsert do conteúdo (mantém tokens e canais que tenha configurado)
3. Em poucos segundos a produção tem a Maria SDR AI com as cores Consenso, prompt novo, e knowledge base atualizada
4. Aplica-se também à Abby, StayLocal e Tejo — cada vez que evoluímos um system_prompt ou KB, o próximo deploy refresca em produção automaticamente

## v3.12 (2026-02) — Analytics avançada + typing adaptativo + 4 agentes openai

## v3.12 (2026-02) — Analytics avançada + typing adaptativo + 4 agentes openai

### Analytics avançada por agente (P1 · concluído)
**Backend** — novo `GET /api/agents/{id}/analytics?days=30`:
- `totals` — conversations, messages, leads, conversion_rate
- `daily_series` — array com exatamente `days` entradas (preenche dias vazios com 0)
- `qualification_breakdown` — quente/morno/frio/outros (via `convo.qualification.status` e `convo.tags`)
- `top_icebreakers` — top 8 primeiras mensagens dos visitantes, com `opens/leads/rate`
- `funnel` — 4 etapas (Visitantes → Engajados 3+ msgs → Qualificados → Leads capturados)
- Clamping rigoroso: `days ∈ [1, 365]`, default 30
- 404 quando agente não pertence ao tenant

**Frontend** — nova página `/app/analytics` (entre Painel e Caixa no menu):
- Selector de agente + período (7/30/90 dias) + botão Recarregar
- 4 cards KPI: Conversas, Mensagens, Leads, Taxa de conversão
- LineChart "Evolução diária" (conversas vs leads)
- Cards "Qualificação de leads" (chips Quente/Morno/Frio/Sem classificação com barras de progresso)
- BarChart horizontal "Funil de conversão" com % drop-off entre etapas
- Tabela "Top frases de abertura" (rate badge verde/laranja/cinza)

### Typing adaptativo no widget (P2 · concluído)
`widget.html::send()` reescrito com **queue de chars** + `setTimeout` drain:
- ≥160 chars esperados → 5 chars/tick @ 8ms (catch-up rápido)
- 40–160 chars → 2 chars/tick @ 18ms
- <40 chars → 1 char/tick @ 35ms (deliberado, humano)
- Catch-up automático se queue > 80 chars (8 chars/tick @ 6ms)
- Resultado: sensação de "humano a escrever" sem cansar utilizador em respostas longas

### DB hygiene + agentes uniformizados (P0 · concluído)
- **Apagados 13 agentes duplicados** (10 "Assistente Principal" do tenant principal + 3 em tenants de teste)
- **DB final: exatamente 4 agentes de produção** (Abby, Maria, StayLocal, Tejo)
- **Todos os 4 agentes** agora com `api_provider="openai"` + `gpt-4o-mini` → todos suportam streaming nativo
- **bootstrap.py** atualizado para que futuros deploys arranquem com `openai` por defeito (em vez de `emergent`)

### Validação automatizada (testing_agent_v3_fork — iteration_12)
- ✅ **11 novos testes analytics** em `test_agent_analytics.py` (shape, days clamping, 404, auth, streaming regression)
- ✅ Frontend: 15/15 data-testids presentes (selectors, KPIs, gráficos, qual chips, icebreakers rows)
- ✅ Streaming smoke (todos os 4 agentes): chunks Abby=11, Maria=38, StayLocal=33, Tejo=40
- ✅ Pre-deploy final: TTFT Maria **0.98s**, 8 chunks, total 1.30s
- ✅ **70/70 pytest passed** / 0 failed / 42 skipped
- ✅ Deployment Agent: **PASS** — pronto para K8s production

## v3.11 (2026-02) — Streaming SSE de tokens em tempo real

## v3.11 (2026-02) — Streaming SSE de tokens em tempo real

### Streaming token-by-token (P1 · concluído)
A perceived latency do chat colapsou de ~4s para **~600ms** ao primeiro token via Server-Sent Events.

**Backend**:
- Novo endpoint `POST /api/webchat/{tenant_id}/stream` — SSE com `text/event-stream`
- 3 tipos de eventos: `ready` (imediato, com `conversation_id`) → `chunk` (text deltas) → `done` (reply completo, follow_up, cards). Erros chegam como `error` (não 500).
- Header `X-Accel-Buffering: no` desativa buffering do nginx — chunks chegam ao cliente sem espera
- **`ai/router.py::llm_stream()`** usa `openai.AsyncOpenAI(stream=True)` direto (fora do `LlmChat`)
- **`ai/orchestrator.py::generate_response_stream()`** + helper `_extract_partial_reply()` que **extrai o campo `"reply"` JSON incrementalmente** (state machine que tolera escapes `\\n \\t \\"` e Unicode `\\uXXXX`) — permite streaming SEM mudar o contrato JSON existente
- Mesma paralelização anterior (`analyze + retrieve + history` em `asyncio.gather`) + fast-path regex + `execute_actions` em background

**Frontend (`widget.html`)**:
- `send()` reescrito: usa `fetch + ReadableStream` para consumir SSE
- Quando o **primeiro chunk** chega → typing-dots desaparece e bubble do bot é criada vazia
- Cada chunk faz `bubble.textContent += delta` — utilizador vê o texto a ser escrito letra-a-letra
- Após `done`: typing-dots curtos (600ms) e renderiza follow-up + cards
- **Fallback automático para `/message`** se SSE falhar (5xx, CORS, drop) — zero downtime UX

**Métricas reais** (Maria SDR via Cloudflare/k8s pública):
| Métrica | Antes (v3.10) | Agora (v3.11) | Ganho |
|---|---|---|---|
| Time To First Token | ~4.0s | **0.61s** | **-85%** |
| Total response time | ~4.0s | ~2.0s | -50% |
| Subjective UX | "esperar" | "conversa fluida" | ✨ |

**Validação automatizada (testing_agent_v3_fork — iteration_11)**:
- ✅ Backend pytest: **6/6 novos** (404 tenant, error SSE bad agent, happy-path event ordering, TTFT 611ms, DB persistence pós-stream, regressão `/message`)
- ✅ Backend full suite: **53/53** sem regressões
- ✅ Frontend: streaming + fallback paths verificados cross-domain
- ✅ Widget render token-by-token em domínio externo (`example.com`)
- **success_rate: backend=100%, frontend=100%**

### Backlog identificado (não bloqueante)
- ⚠️ `GET /api/widget/{tenant_id}` (raw view) não injeta `?tenant=` na query — utilizadores que abram este endpoint diretamente veem widget vazio. Funcionamento normal via `widget.js` + `data-*` ou `widget-test/{tid}/{aid}` não é afetado.

## v3.10 (2026-02) — Maria SDR AI + latência reduzida

## v3.10 (2026-02) — Maria SDR AI + latência reduzida

### Maria SDR AI (P0 · concluído)
A Maria foi reposicionada de "consultora digital" genérica para **SDR AI consultiva B2B** ao serviço da landing page `consenso-shop.eu`. 5 missões:
1. **EDUCAR** — agentes IA multilingue Consenso, 24/7, 6+ idiomas, Web + WhatsApp + IG + Messenger + Telegram
2. **VENDER adaptando ao perfil** — CEO=ROI · Marketing=leads · IT=integração · Imobiliária=qualificação
3. **QUALIFICAR conversacional** — nome → empresa → setor → dor → volume → email (uma pergunta de cada vez)
4. **FECHAR** — propor demo/reunião + dispara `create_lead` quando tem nome+empresa+email
5. **DEMO MODE** — simulação imobiliária em 4 fases (compra/arrendamento → tipologia → imóveis → marcação)

**Configuração** (`/app/backend/seed_maria.py`):
- Nome: "Maria — Consenso SDR AI"
- Welcome: "Olá! 👋 Sou a Maria, consultora digital da Consenso. Em que posso ajudar o teu negócio hoje?"
- Avatar: photo de mulher profissional (consenso-shop hero)
- **Tema atualizado**: azul `#4591CE` (primary) + amarelo `#E4AC1E` (bot accent) — cores oficiais Consenso
- KB com 12 chunks: empresa, problemas, processo, idiomas, features, preços, integração, canais, casos de uso, contacto
- Provider: **OpenAI direto** (`gpt-4o-mini`) usando `OPENAI_API_KEY` do env
- Icebreakers SDR: "Ver planos e preços · Como funciona para imobiliárias · Pedir demonstração real · Quantos idiomas suporta · Como integra com o meu site · Qual o ROI esperado"

**Validação automatizada (8 cenários SDR cold sessions)**:
| Cenário | Latência | Comportamento |
|---|---|---|
| Educate · saudação | 3.89s | CTA pergunta soft |
| Educate · explicação | 3.43s | 24/7 multilingue |
| Educate · preços | 3.14s | Link planos |
| Qualify · interesse | 4.45s | Qualificação automática |
| Qualify · followup | 5.24s | Resolve fora-de-horas |
| Convert · demo | 3.24s | Pede nome+empresa |
| Persona · CEO ROI | 4.94s | ROI + custos |
| Persona · IT integração | 4.56s | 1 linha de código |
| **AVG** | **4.11s** | ✅ dentro 3-5s |

### Optimizações de latência (P0 · concluído)
**De 4.07s → 3.85s → 3.53s avg** ao paralelizar tarefas independentes:
1. **`analyze` + `retrieve` + `history-fetch` em paralelo** (`asyncio.gather`) — 3 chamadas independentes que antes eram sequenciais
2. **`execute_actions` + CRM qualification em background** — o utilizador vê a resposta imediatamente; a criação de leads/tickets e a qualificação correm em `asyncio.create_task` após o broadcast
3. **Fast-path expandido em `analyze.py`** — heurísticas regex para: greeting (já existia), real-estate query (já existia), complaint, support, generic inquiry curta (< 200 chars). LLM analyze só é chamado para mensagens longas (>= 200 chars) sem sinais claros — corte de 70-80% das chamadas LLM analyze

### `_agent_is_configured` aceita env vars (P1 · concluído)
Quando `api_provider="openai"` e `api_key=""`, o agente agora valida com sucesso se `OPENAI_API_KEY` estiver no env. Permite agentes managed-by-platform sem necessidade de paste manual de tokens.

### Pre-deploy checkup v3.10
- ✅ Supervisor (backend, frontend, mongodb) RUNNING
- ✅ Auth + 5 endpoints chave (200)
- ✅ Widget origin injection bullet-proof
- ✅ Maria SDR cold reply em 4.82s (alvo 3-5s)
- ✅ **53 pytest passed** / 0 failed / 42 skipped
- ✅ Sem hardcoding de URLs preview no código
- ✅ Cross-domain widget testado em domínio externo

## v3.9 (2026-02) — Dashboard "Saúde dos canais" + pre-deploy checkup

## v3.9 (2026-02) — Dashboard "Saúde dos canais" + pre-deploy checkup

### Novo painel "Saúde dos canais" (P0 · concluído)
Antes do v3.9 o cliente tinha de abrir cada agente individualmente para perceber se cada canal estava ligado. Agora há uma visão consolidada em `/app/painel` por baixo dos charts existentes.

**Backend**:
- Refactor: `agent_test_channel` extraiu a lógica de provider em `_run_channel_test(channel, ch)` (puro — sem DB writes), e o handler público passa a **persistir** `last_test_at`/`last_test_ok`/`last_test_info`/`last_test_error` em `agent.channels.{channel}.*` após cada chamada de teste.
- Novo endpoint `GET /api/agents/health` (read-only, JWT) — devolve para cada agente ativo do tenant: `{id, name, avatar_url, channels:[{channel, enabled, configured, last_test_at, last_test_ok, last_test_info, last_test_error}]}` com os 5 canais (webchat, whatsapp, telegram, instagram, messenger). `configured=true` quando todos os campos obrigatórios do canal estão preenchidos (sem fazer ping ao provider).

**Frontend (`Painel.jsx`)**:
- Novo componente `<ChannelHealth />` mostrado abaixo dos charts existentes (data-testid: `channel-health`)
- 1 card por agente com avatar/iniciais + contador "X / Y ligados"
- 5 chips por agente (1 por canal): ícone + label + estado colorido + último teste relativo + info/erro do provider + botão "Testar agora" (excepto webchat)
- Estados: `Inativo` (cinza), `Configuração incompleta` (laranja), `Ligado` (verde), `Falha` (vermelho), `Ativo · sem handshake` (azul)
- Botão "Recarregar" no canto superior direito do card
- Helper `formatRelative()` para "agora mesmo" / "há X min/h/dias"

**Validação automatizada (testing_agent_v3_fork — iteration_10)**:
- ✅ Backend: 9/9 novos testes em `test_health_dashboard.py` (auth, shape, 5 canais, telegram persiste falha, disabled retorna mensagem PT, unknown channel não dá 500, regressão widget e dashboard/stats)
- ✅ Backend completo: **44 passed / 42 skipped** (suite v3 ativa) sem regressões
- ✅ Frontend Playwright: card por agente, chips com estados corretos, "Testar agora" persiste estado e atualiza UI
- ✅ Sem regressões em widget cross-domain, gpt-4o-mini latency 2.65s, ou canais sociais
- **success_rate: backend=100%, frontend=100%**

### Pre-deploy checkup (P0 · concluído — 8/8 verde)
| # | Verificação | Estado |
|---|---|---|
| 1 | Supervisor (backend, frontend, mongodb, nginx) | ✅ RUNNING |
| 2 | `.env` protegidas (`MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `EMERGENT_LLM_KEY`, `OPENAI_API_KEY`) | ✅ SET |
| 3 | `REACT_APP_BACKEND_URL` | ✅ SET |
| 4 | Auth + endpoints chave (`/agents`, `/agents/health`, `/dashboard/stats`, `/conversations`, `/leads`, `/widget.js`, `/widget/{tid}`) | ✅ HTTP 200 |
| 5 | Widget origin injection (`__CP_ORIGIN__` → backend domain) | ✅ Funciona |
| 6 | Latência IA (Maria, gpt-4o-mini) | ✅ 2.65s |
| 7 | Health endpoint sample (4 agentes × 5 canais) | ✅ |
| 8 | Pytest backend suite | ✅ 44 passed |

### Como o cliente põe live (3 passos)
1. **Telegram**: criar bot no @BotFather → colar `bot_token` → guardar → chamar `setWebhook` com a URL exibida
2. **WhatsApp Cloud**: na Meta Business Manager, criar app + número → colar `access_token`, `phone_number_id`, `verify_token` → configurar webhook
3. **Instagram + Messenger**: na Meta App, ativar Webhooks (objeto `instagram` e `page`, campos `messages`) → colar `page_access_token` + `ig_user_id`/`page_id` + `verify_token` → testar ligação



## v3.8 (2026-02) — Omni-canal 100% live (Instagram + Messenger)

### Novos canais (P0 · concluído)
Antes do v3.8 só Webchat, WhatsApp e Telegram tinham webhooks reais. Instagram e Messenger estavam marcados "Brevemente". Agora os 4 canais sociais funcionam end-to-end via **Meta Graph API v20.0**.

**Backend (`/app/backend/webhooks.py`)** — novas rotas por agente:
- `GET /api/webhooks/instagram/{tenant_id}/{agent_id}` — Meta hub verification
- `POST /api/webhooks/instagram/{tenant_id}/{agent_id}` — recebe `entry[].messaging[]` (objeto IG), processa via IA, responde via `POST /v20.0/{ig_user_id}/messages`
- `GET /api/webhooks/messenger/{tenant_id}/{agent_id}` — Meta hub verification
- `POST /api/webhooks/messenger/{tenant_id}/{agent_id}` — recebe `entry[].messaging[]` (objeto page), processa via IA, responde via `POST /v20.0/me/messages` com `messaging_type=RESPONSE`
- Helpers `_send_messenger`, `_send_instagram` (mesma assinatura do `_send_whatsapp`)

**Backend (`server.py`)** — novos casos no `agent_test_channel`:
- `instagram` valida `page_access_token` + `ig_user_id` chamando `GET /v20.0/{ig_user_id}` (devolve `@username`)
- `messenger` valida `page_access_token` + `page_id` chamando `GET /v20.0/{page_id}` (devolve nome + categoria)
- Validação per-agente igual ao WhatsApp (não há tokens globais)

**Frontend (`Agentes.jsx` separador Canais)**:
- Removido bloco "comingSoon" para Instagram e Messenger
- Cada canal tem 3 inputs: `page_access_token` (password), `ig_user_id`/`page_id` (text), `verify_token` (text)
- Webhook URL gerado dinamicamente + botão "Copiar"
- Hint contextual: "Adicione este URL nas Webhook Subscriptions da App Meta (objeto: instagram | page · campos: messages)"
- Botão "Testar ligação" chama `/test-channel/{instagram|messenger}` em tempo real

**Validação automatizada (testing_agent_v3_fork — iteration_9)**:
- ✅ Backend pytest: **14/14 passed** (verify GET sucesso/403, POST inbound com payload Meta real, test-channel devolve "Invalid OAuth access token" da Meta com tokens FAKE — prova que chegamos à Graph API)
- ✅ Frontend Playwright: 5 canais visíveis (`channel-webchat`, `channel-whatsapp`, `channel-telegram`, `channel-instagram`, `channel-messenger`), inputs e webhook URLs aparecem ao ativar
- ✅ Sem regressões em widget cross-domain ou latência gpt-4o-mini
- **success_rate: backend=100%, frontend=100%**

### Como o cliente põe live (3 passos)
1. **Telegram**: criar bot no @BotFather → colar `bot_token` → guardar → chamar `setWebhook` com a URL exibida
2. **WhatsApp Cloud**: na Meta Business Manager, criar app + número → colar `access_token`, `phone_number_id`, `verify_token` → configurar webhook
3. **Instagram + Messenger**: na Meta App, ativar Webhooks (objeto `instagram` e `page`, campos `messages`) → colar `page_access_token` + `ig_user_id`/`page_id` + `verify_token` → testar ligação



## v3.7 (2026-02) — Widget bullet-proof cross-domain + LLM rápido (gpt-4o-mini)

### Bug fix · Iframe do widget mostrava 404 no consenso-shop.eu (P0 · concluído)
**Sintoma**: ao clicar no ícone de chat no `consenso-shop.eu` (WordPress + LiteSpeed Cache), o iframe abria a página do próprio `consenso-shop.eu` (404 "The Page Can't Be Found") em vez do widget Consenso+.

**Causa raiz**: o `widget.js` resolvia o `origin` a partir de `script.src`, mas plugins WP (LiteSpeed, Cloudflare) podem reescrever `<script src>` como caminho relativo. O fallback `location.origin` apontava então para o domínio do site host → iframe carregava `https://consenso-shop.eu/api/widget/...` → 404.

**Correções aplicadas**:
1. **Backend (`server.py`)**: endpoint `GET /api/widget.js` agora **injeta o origin absoluto** no JS no momento de servir (`__CP_ORIGIN__` → `https://<host>`). Funciona em qualquer ambiente (preview ou produção) via `x-forwarded-host`.
2. **Frontend (`widget.js`)**: nova ordem de prioridade na resolução do origin:
   - `__CP_ORIGIN__` injetado pelo servidor (bullet-proof)
   - Atributo `data-origin` no `<script>` (override manual)
   - Parsing de `script.src` (legado)
   - `location.origin` (último recurso)
3. Cache `max-age=60` (em vez de 300) para invalidação mais rápida em produção.

**Validação cross-domain** (Playwright em `example.com`):
- ✅ Widget injetado em domínio externo
- ✅ Iframe SRC = `https://<backend>/api/widget/...` (correto)
- ✅ Chat abre com avatar Maria + theme gold/blue + icebreakers

### Latência da IA reduzida para 3-5s (P0 · concluído)
**Antes**: respostas em ~8-13s (mistura Emergent Universal Key + lógica em background).
**Agora**: respostas em **2.67s–4.82s** consistentemente.

**Configuração final**:
- Chave OpenAI direta no `backend/.env` (`OPENAI_API_KEY`, fornecida pelo cliente)
- `ai/router.py` força **`gpt-4o-mini` em todos os tasks** (`reasoning`, `long_context`, `fast`, `fallback`)
- Resolução de chave: BYO key do agente → `OPENAI_API_KEY` env → fallback Universal Key

**Benchmark via curl** (preview, 10/02/2026):
| Agente | Query | Latência | Cards |
|---|---|---|---|
| Maria | "Olá" | 3.45s | 0 |
| Maria | "O que é um agente IA?" | 4.82s | 0 |
| Maria | "Quero ver uma demo" | 3.82s | 0 |
| Abby | "Olá" | 2.67s | 0 |
| Abby | "T2 em Lagos até 400k" | 3.08s | 1 |
| Abby | "moradia V4 Braga" | 3.24s | 1 |

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
