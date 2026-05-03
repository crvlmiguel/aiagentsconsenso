# Consenso Plus — PRD (v2.1)

## Problem statement
MVP existente com falhas: erros "AI service unavailable", API config em falta, canais não configuráveis, sem modo de teste interno, integrações CRM imaturas.

## v2.1 (2026-05-03) — Fix pack funcional
- **Configuração API por agente**: Provider (Chave Universal Emergent / OpenAI / Anthropic / Gemini), Modelo, Chave API (com mostrar/ocultar), botão "Testar ligação" (ping real ao provider)
- **Validação de agente antes de executar**: se sem chave → HTTP 400 + PT "Por favor configure a API da IA para ativar o agente."
- **Modo Testar chatbot**: slide-over com chat em direto que usa o pipeline real (intent + structure + retrieval + resposta + cards) — mesma configuração que produção
- **Configuração por canal**: diálogos com campos específicos por kind (WA: access_token+phone_number_id+webhook URL; IG: access_token+page_id; Telegram: bot_token+webhook URL; Messenger: access_token+page_id; Webchat: toggle + snippet)
- **Validação obrigatória no PUT /api/integrations**: `Configuração incompleta. Campos em falta: ...`
- **SMTP completo** + botão "Enviar email de teste"
- **Notificação automática de novos leads** por email (quando SMTP ligado + `notify_email` configurado no agente ou na integração)
- **CRMs "Em breve"**: HubSpot / Pipedrive / Salesforce / Webhook com badge âmbar + botão disabled
- Erros LLM propagam via exceções `LLMConfigMissing` / `LLMProviderError` em PT

## Test credentials
demo@consenso.plus / demo1234 (Imobiliária Lisboa)

## Testing subagent — iteração 3
- Backend: **13/13 passes**
- Frontend: 100% dos fluxos v2.x verificados ao vivo
- Nenhum blocker; 1 observação minor (config merge em PUT /integrations mantém campos antigos quando `config:{}` é enviado — OK para UI atual)

## Backlog P0
- Webhook real Telegram `/api/webhooks/telegram/{tenant_id}` (mais rápido de ligar)
- Webhook real WhatsApp Cloud
- WebSocket: reconectar automaticamente

## Backlog P1
- Mover WIDGET_HTML para ficheiro estático
- Split `server.py` em routers (já >900 linhas)
- Extrair `REQUIRED_FIELDS_BY_KIND` para `models.py` (partilhar backend/frontend)
- Vector embeddings (Mongo Atlas Search)
- CRMs reais via OAuth

## Backlog P2
- Rate limiting no `/api/test-connection` (evitar uso como validity oracle)
- Multi-agente com routing por regras/tags
- Stripe usage billing
- SLA nos tickets
