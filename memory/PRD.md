# Consenso Plus — PRD (v2.2)

## v2.2 (2026-05-03) — Reliability pass

### Correções / melhorias
- **Mensagens de erro unificadas**: todos os erros de IA usam agora a copy "API da IA não configurada ou inválida." (PT-PT). Adeus mensagens genéricas em inglês.
- **Retrieval corrigido**: termos com 2 caracteres já são indexados (bug que eliminava "T3", "T1", "BD") + filtro de stopwords PT
- **Orquestrador mais rígido**: prompt reforçado com EXEMPLO explícito de JSON output + regras obrigatórias sobre cards (NUNCA inventar; SEMPRE devolver cards quando há itens recuperados). Task LLM forçado para "reasoning" quando há contexto recuperado (para citação fiável).
- **Retry + "Configurar API →"** no painel "Testar chatbot" quando ocorre erro; o botão leva diretamente ao painel de config do agente.
- **Validação de canais** continua bloqueada sem config válida (Instagram exige access_token+page_id, WhatsApp exige access_token+phone_number_id, etc.).

### Verificação end-to-end (curl)
- [x] Agente sem chave API → 400 "API da IA não configurada ou inválida. Por favor configure a API da IA para ativar o agente."
- [x] Canal sem config → 400 "Configuração incompleta. Campos em falta: ..."
- [x] Pipeline completo devolve **cards reais** (título + preço + imagem + link) copiados dos items recuperados. Testado: "Quero T3 em Lisboa" → T3 Campo de Ourique; "Cascais vista mar" → T4 Cascais; "T1 Príncipe Real" → T1 Príncipe Real.
- [x] WebSocket `/api/ws/{tenant_id}` aceita ligações
- [x] SMTP test devolve erro específico sem 500
- [x] Inbound simulation cria lead com tags automáticas ("sales_inquiry", "sales") + envia cards + deteção de idioma pt

### Áreas intocáveis
- Páginas `/iniciar-sessao`, `/registar`, AuthProvider, JWT — NÃO alteradas nesta passagem conforme pedido

## Backlog P0
- Webhook real Telegram `/api/webhooks/telegram/{tenant_id}`
- Webhook real WhatsApp Cloud
- Reconexão automática WebSocket

## Backlog P1
- Vector embeddings (Mongo Atlas Search)
- Move WIDGET_HTML para ficheiro estático
- Split `server.py` em routers (900+ linhas)
- CRMs reais via OAuth

## Backlog P2
- Rate limiting em endpoints públicos
- Multi-agente com routing por tags
- Stripe usage billing
- SLAs nos tickets
