# Consenso Plus — PRD (Product Requirements Document)

## 1. Problema/Objetivo
"CONSENSO PLUS — AI BUSINESS OPERATING SYSTEM": plataforma multi-tenant premium
de agentes IA multilingues para empresas B2B.

## 2. Idioma preferido do utilizador
European Portuguese (pt-PT). Toda a UI, agentes seed, respostas de sistema e
comunicação com o utilizador devem estar em pt-PT.

## 3. Personas
- **Cliente Consenso Plus (Maria — chatbot)**: PMEs a explorar agentes IA para
  Imobiliário, Hotelaria, Turismo, Serviços.
- **Cliente Consenso Global (Clara — chatbot institucional)**: empresas a
  explorar SEO Multilingue, Localização, Copywriting, Consultoria.

## 4. Agentes seedados
| Agente | Marca | Tom | Scheduling link | KB isolada |
|---|---|---|---|---|
| Maria | Consenso Plus | Informal PT-PT | consenso-shop.eu/marcar-reuniao | Sim |
| **Clara** *(novo)* | Consenso Global | **Formal PT-PT** | consensoglobal.pipedrive.com/scheduler/1DzB0QCb/... | Sim |
| Abby / ABBI EN | ABBI Imóveis | Informal | — | Sim |
| StayLocal | Concierge de hotel | Informal multi-lang | — | Sim |
| Tejo Sunset Sailing | Turismo | Informal multi-lang | — | Sim |
| ImmoAI | Demo imobiliário | Informal | — | Sim |

## 5. Requisitos globais (aplicados a TODOS os agentes)
- Deteção + persistência de idioma (sticky, PT/EN/FR/ES/DE/NL/CA).
- Reclassificação de intenção por cada mensagem (anti-loop "Obrigado").
- Uma pergunta por turno.
- Interpretação de respostas curtas ("eu", "sim", "ok").
- Linguagem neutra em género (sem "ajudá-lo", "interessado", etc.).
- Prevenção de loops / respostas duplicadas.
- Fecho de qualificação com resumo → confirmação → acção.
- Fluxo de orçamento (recolha progressiva, confirmação real).
- Whitelist de domínios (configurável por agente).
- Tom configurável por agente (formal/informal).
- Isolamento estrito de RAG por tenant_id + agent.data_source_ids.
- Enforce do link oficial de agendamento (substitui Calendly/etc. inventados).
- Variante PT: perguntar quando o utilizador pede tradução para "português"
  sem indicar variante.

## 6. Requisitos por agente
### Clara — Consenso Global
- Formal PT-PT ("você"), nunca "tu".
- SEO reconhecido como serviço da Consenso Global.
- KB exclusiva Consenso Global (sem imóveis, sem planos Consenso Plus).
- Redirecciona educadamente para Consenso Plus quando o tema é chatbots/planos.

### Maria — Consenso Plus
- Informal PT-PT ("tu").
- Apresenta agentes IA, chatbots à medida, planos, subscrições, consultoria.
- Planos em cartões (starter/pro/enterprise).
- Verticais: Imobiliário, Hotelaria, Turismo, Empresas de Serviços.

## 7. Arquitectura de código
```
/app/backend/
├── server.py          # FastAPI (2600+ linhas — carece refactor para /routes)
├── bootstrap.py       # Provisiona agents; refresca safety fields mesmo em is_customized
├── models.py          # Agent com formality, default_pt_variant, services, quote_form_enabled, qualification_fields
├── seed_maria.py      # Maria (Consenso Plus)
├── seed_clara.py      # ⭐ NOVO — Clara (Consenso Global, formal PT-PT)
├── seed_*.py          # Outros agentes
└── ai/
    ├── orchestrator.py    # generate_response + streaming; passa agent completo
    ├── global_rules.py    # ⭐ Reescrito — config-driven (formality, services, PT variant)
    ├── guardrails.py      # ⭐ Estendido — apply_gender_neutral, ensure_pt_variant_question, enforce_scheduling_link
    ├── memory.py          # ⭐ Estendido — language_variant, ask_pt_variant, scheduling_confirmed
    ├── retrieval.py       # RAG filtrado por data_source_ids do agente (isolamento)
    └── translator.py      # Tradução de agente em background
```

## 8. Guardrails determinísticos (pós-LLM)
Ordem: `scrub_repeated_questions` → `ensure_pt_variant_question` →
`apply_gender_neutral` → `enforce_scheduling_link` → `filter_urls_by_whitelist`
→ `ensure_scheduling_link` (injecção com fallback via `facts.scheduling_confirmed`).

## 9. Testes
- **Pytest** (`/app/backend/tests/`): 158 passed, 23 skipped.
- **Testing agent iteration 19**: 17/17 QA PT-PT + regressão 44/44.

## 10. Backlog priorizado
- **P2 — Refactor server.py** em `/app/backend/routes/` (auth, agents, webchat, admin).
- **P2 — Integrações CRM reais** (HubSpot, Pipedrive, Salesforce).
- **P2 — UI: cartões visuais** dos planos no webchat (frontend widget).
- **P2 — Dashboard**: expor `formality`, `services`, `scheduling_link`,
  `allowed_domains`, `default_pt_variant` na página `Agentes.jsx` para edição
  pelo cliente sem seed.

## 11. Contas de teste
Ver `/app/memory/test_credentials.md`.
