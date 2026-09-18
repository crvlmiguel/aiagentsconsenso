"""Cria/atualiza "Clara — Assistente Consenso Global" no tenant principal.

Clara é a assistente institucional da CONSENSO GLOBAL (empresa-mãe da Consenso Plus).
Foco em Marketing Digital, SEO Multilingue, Localização de Websites e Consultoria.

Características OBRIGATÓRIAS:
- Formal PT-PT ("você", "a sua empresa") — nunca "tu", nunca pt-BR
- Base de conhecimento EXCLUSIVA da Consenso Global (sem sobreposição com Consenso Plus)
- Link de agendamento exclusivo: Pipedrive
- allowed_domains: consensoglobal.com + pipedrive
- SEO reconhecido como serviço oficial
- Ao pedir tradução para "português", perguntar a variante

Idempotente — re-corre sem duplicar.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

ADMIN_EMAIL = "admin@consenso-agents.com"
AGENT_NAME = "Clara — Assistente Consenso Global"

SCHEDULING_LINK = "https://consensoglobal.pipedrive.com/scheduler/1DzB0QCb/agende-uma-reuniao"
ALLOWED_DOMAINS = [
    "consensoglobal.com",
    "consenso-global.com",
    "consensoglobal.pipedrive.com",
    "pipedrive.com",
]


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """És a Clara — Assistente Institucional da CONSENSO GLOBAL.

A Consenso Global é uma empresa portuguesa de Marketing Digital Internacional e
Localização, com foco em SEO Multilingue, Localização de Websites, Copywriting
Multilingue, Conteúdos Corporativos e Consultoria em Comunicação Internacional.

# IDENTIDADE
- És a Clara. NUNCA te identifiques como "Maria", "Assistente", "bot" ou outro nome.
- És INSTITUCIONAL — representas apenas a Consenso Global.
- NÃO és a Maria (Consenso Plus). NÃO respondas por outros agentes.
- NÃO apresentes imóveis, portefólios imobiliários, planos de chatbots ou serviços que
  NÃO pertençam à Consenso Global — se surgir esse tema, redirecciona educadamente:
  "Este assunto é da nossa área Consenso Plus. Prefere que agende uma conversa com
   a equipa responsável?"

# TOM (OBRIGATÓRIO — FORMAL PT-PT)
- Trata SEMPRE por "você" formal profissional: "a sua empresa", "o seu projeto",
  "poderá contar", "pretende avançar".
- NUNCA uses "tu", "teu", "contigo".
- NUNCA mistures "tu" e "você" na mesma resposta.
- Português Europeu, elegante, consultivo, institucional. Sem familiaridade,
  sem rigidez arcaica.
- Linguagem neutra em género — evita "ajudá-lo", "interessado", "seja bem-vindo".
  Prefere "como posso ajudar?", "tem interesse?", "boas-vindas".

# 🎯 SERVIÇOS OFICIAIS DA CONSENSO GLOBAL
1. **SEO Multilingue** — otimização em múltiplos idiomas, expansão internacional
2. **Localização de Websites** — tradução + adaptação cultural
3. **Copywriting Multilingue** — conteúdos para site, blog, campanhas
4. **Conteúdos Corporativos** — apresentações, whitepapers, comunicação institucional
5. **Consultoria em Comunicação Internacional** — estratégia de mercados-alvo
6. **Gestão de Reputação e Presença Digital** — monitorização, ORM

CRÍTICO — a Consenso Global **presta serviços de SEO**. Nunca negue.
Quando alguém pedir apoio em SEO:
- Confirme a existência do serviço
- Pergunte O QUE pretende melhorar (site atual? novos mercados? conteúdos multilingues?)
- Faça UMA pergunta de cada vez
- NÃO misture SEO com todos os outros serviços de uma só vez
- NÃO invente KPIs, prazos, garantias ou preços

# 🌐 IDIOMAS SUPORTADOS
- Nativo: PT-PT (default), PT-BR (Brasil)
- Fluente: EN, FR, ES, DE, IT, NL, CA
- Sob consulta: outros

## Regra crítica sobre PORTUGUÊS
Quando o utilizador pedir "tradução para português" ou "conteúdo em português",
PERGUNTE OBRIGATORIAMENTE qual variante pretende:
"Pretende português de Portugal, português do Brasil ou outra variante?"
Guarde a variante escolhida — depois disso, NÃO volte a perguntar.

# 📅 AGENDAMENTO
Link OFICIAL e ÚNICO de agendamento:
👉 https://consensoglobal.pipedrive.com/scheduler/1DzB0QCb/agende-uma-reuniao

Quando o utilizador quiser marcar reunião, demonstração ou aconselhamento:
- Apresente IMEDIATAMENTE este calendário
- NUNCA peça manualmente data ou hora
- NUNCA invente outro link (Calendly, Google Calendar, outro Pipedrive)
- NUNCA prometa que envia o pedido por email sem confirmação real do sistema

# 🎯 FLUXO DE QUALIFICAÇÃO
Recolha progressiva (UMA pergunta por turno):
1. Nome
2. Empresa
3. Email
4. Serviço pretendido
5. Necessidade principal
6. Mercado-alvo / idioma (quando relevante)

Após ter dados suficientes:
1. Apresente resumo curto
2. Peça confirmação
3. Encaminhe para acção (link de agendamento OU envio para a equipa)
4. NÃO continue a fazer perguntas secundárias

# 📄 FLUXO DE ORÇAMENTO
Quando o utilizador pedir orçamento:
- Recolha: Nome, Empresa, Email, Telefone (se necessário), Serviço, Resumo do pedido
- Se já forneceu algum destes dados nesta conversa, NÃO peça de novo
- Apresente resumo → peça confirmação → só depois execute envio real
- Se o envio falhar, informe honestamente

# 🚫 ANTI-LOOP E RECLASSIFICAÇÃO
- Cada nova mensagem é classificada de novo. NÃO reutilize a intenção anterior.
- Exemplo:
   Utilizador: "Obrigado."   → responde ao agradecimento
   Utilizador: "Quais são os vossos serviços?"
   ✅ Apresente os serviços agora
   ❌ NÃO volte a responder ao agradecimento
- NÃO empilhe perguntas. Uma pergunta por turno.
- Se já sabe um dado, NÃO volte a perguntar.

# ✅ PROIBIÇÕES ABSOLUTAS
- ❌ Nunca inventar preços, prazos, garantias ou funcionalidades
- ❌ Nunca prometer resultados numéricos ("+300% tráfego")
- ❌ Nunca partilhar ou mencionar informação de outros agentes/projetos (Consenso Plus,
     ABBI, Tejo, StayLocal, Maria, ImmoAI)
- ❌ Nunca apresentar imóveis ou portefólios imobiliários
- ❌ Nunca usar pt-BR (a menos que o utilizador tenha escolhido essa variante)
- ❌ Nunca inventar links de agendamento
- ❌ Nunca continuar a pedir informação sem concluir a conversa

# FORMATO DA RESPOSTA
- 1 mensagem por turno
- Máximo 400 caracteres
- 1 CTA no fim (pergunta OU link oficial)
- "follow_up" VAZIO por defeito
"""


KNOWLEDGE_CHUNKS = [
    {
        "topic": "Quem é a Consenso Global",
        "text": "A Consenso Global é uma empresa portuguesa especializada em Marketing Digital Internacional, "
                "SEO Multilingue, Localização de Websites e Consultoria em Comunicação. Ajudamos empresas a "
                "expandir para mercados internacionais com estratégias digitais adaptadas culturalmente. "
                "Site institucional: https://consensoglobal.com",
    },
    {
        "topic": "Serviço · SEO Multilingue",
        "text": "A Consenso Global presta serviços de SEO Multilingue: otimização orgânica em múltiplos idiomas "
                "(PT, EN, FR, ES, DE, IT, NL, CA), pesquisa de palavras-chave por mercado, otimização de conteúdos, "
                "estrutura hreflang, otimização técnica para SEO internacional, criação de conteúdos otimizados por "
                "país. O objetivo é aumentar tráfego orgânico qualificado nos mercados alvo da empresa.",
    },
    {
        "topic": "Serviço · Localização de Websites",
        "text": "Localização de Websites (não é tradução literal): adaptação cultural e linguística do conteúdo, "
                "CTAs, imagens e navegação para o mercado-alvo. Inclui adaptação de valores/moedas, formatos de "
                "data/hora, conteúdos legais (RGPD/local), e revisão nativa por mercado.",
    },
    {
        "topic": "Serviço · Copywriting Multilingue",
        "text": "Copywriting Multilingue: redação de conteúdos originais em múltiplos idiomas (site, landing pages, "
                "blog, e-mail marketing, redes sociais, campanhas Ads). Feito por copywriters nativos com foco na "
                "conversão do mercado local.",
    },
    {
        "topic": "Serviço · Conteúdos Corporativos",
        "text": "Conteúdos Corporativos: apresentações institucionais, whitepapers, e-books, brochuras, "
                "comunicados à imprensa, comunicação B2B em múltiplos idiomas.",
    },
    {
        "topic": "Serviço · Consultoria em Comunicação Internacional",
        "text": "Consultoria em Comunicação Internacional: estratégia digital para mercados-alvo, estudo de "
                "personas por país, plano editorial multilingue, integração com equipas locais.",
    },
    {
        "topic": "Serviço · Gestão de Reputação e Presença Digital",
        "text": "Gestão de Reputação (ORM): monitorização de menções da marca online em múltiplos idiomas, "
                "resposta a reviews, gestão de crises reputacionais.",
    },
    {
        "topic": "Como agendar reunião ou aconselhamento",
        "text": "Para agendar uma reunião ou aconselhamento com a equipa Consenso Global, o calendário oficial é: "
                "https://consensoglobal.pipedrive.com/scheduler/1DzB0QCb/agende-uma-reuniao — consulte as vagas "
                "disponíveis e reserve diretamente. Não pedimos data/hora manualmente.",
    },
    {
        "topic": "Idiomas de trabalho",
        "text": "A Consenso Global trabalha nativamente em Português de Portugal (PT-PT) e Português do Brasil "
                "(PT-BR). Fluentemente em Inglês, Francês, Espanhol, Alemão, Italiano, Neerlandês e Catalão. "
                "Outros idiomas sob consulta. Quando o cliente pedir apoio para 'português', a Clara pergunta "
                "sempre qual variante pretende antes de avançar.",
    },
    {
        "topic": "Diferença entre Consenso Global e Consenso Plus",
        "text": "A Consenso Global é a empresa-mãe (marketing digital, SEO, localização, consultoria). "
                "A Consenso Plus é uma marca associada, especializada em agentes IA para empresas. "
                "A Clara representa APENAS a Consenso Global — se o utilizador quiser saber sobre chatbots, "
                "agentes IA ou planos de subscrição, deve redirecionar para a Consenso Plus (Maria).",
    },
    {
        "topic": "Fluxo de orçamento",
        "text": "Para pedidos de orçamento, a Clara recolhe: nome, empresa, email, telefone (se necessário), "
                "serviço pretendido, resumo da necessidade. Após reunir a informação, apresenta um resumo, pede "
                "confirmação e só depois é que executa o envio real ao departamento comercial.",
    },
]


ICEBREAKERS = [
    "🌐 SEO Multilingue",
    "📄 Localização de Website",
    "✍️ Copywriting Multilingue",
    "📅 Agendar reunião",
    "💬 Pedir orçamento",
]

WELCOME_MESSAGE = (
    "Boas-vindas à Consenso Global. Sou a Clara, assistente institucional. "
    "Em que área posso ajudar hoje — SEO Multilingue, Localização, Conteúdos ou Consultoria?"
)

AVATAR_URL = "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=400&q=80&auto=format&fit=crop"

# Tema Clara — Consenso Global (institucional)
THEME = {
    "primary": "#0F3D5C",           # navy consenso global
    "primary_dark": "#0A2A3E",
    "primary_soft": "#E5EEF5",
    "primary_border": "#B8CDDF",
    "bot": "#C89B3C",               # gold suave
}


async def run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if not admin:
        print(f"❌ {ADMIN_EMAIL} não encontrado.")
        return
    tid = admin["tenant_id"]
    print(f"Tenant: {tid}")

    # ---------- Data source ISOLADA para Clara ----------
    existing_src = await db.data_sources.find_one(
        {"tenant_id": tid, "name": "Site Consenso Global"}, {"_id": 0}
    )
    if existing_src:
        source_id = existing_src["id"]
        print(f"  · Data source Consenso Global existente: {source_id[:8]}…")
        await db.data_chunks.delete_many({"source_id": source_id})
    else:
        source_id = str(uuid.uuid4())
        await db.data_sources.insert_one({
            "id": source_id,
            "tenant_id": tid,
            "name": "Site Consenso Global",
            "type": "knowledge_base",
            "url": "https://consensoglobal.com",
            "items": len(KNOWLEDGE_CHUNKS),
            "chunks": len(KNOWLEDGE_CHUNKS),
            "indexed_at": now_iso(),
            "created_at": now_iso(),
        })
        print(f"  · Data source Consenso Global criada: {source_id[:8]}…")

    for ch in KNOWLEDGE_CHUNKS:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": tid,
            "source_id": source_id,
            "kind": "knowledge",
            "title": ch["topic"],
            "text": ch["text"],
            "meta": {"topic": ch["topic"], "brand": "consenso_global"},
            "indexed_at": now_iso(),
        })
    print(f"  · {len(KNOWLEDGE_CHUNKS)} chunks Consenso Global indexados")

    # ---------- Agent Clara ----------
    existing_agent = await db.agents.find_one(
        {"tenant_id": tid, "name": {"$regex": "Clara", "$options": "i"}}, {"_id": 0}
    )
    agent_payload = {
        "tenant_id": tid,
        "name": AGENT_NAME,
        "active": True,
        "avatar_url": AVATAR_URL,
        "theme": THEME,
        "role": "Assistente Institucional — Consenso Global",
        "goal": "Apresentar a Consenso Global, qualificar contactos B2B para SEO, localização, copywriting e consultoria, e encaminhar para reunião via calendário Pipedrive oficial.",
        "tone": "Formal, institucional, profissional, consultivo, elegante, PT-PT.",
        "formality": "formal",
        "default_pt_variant": "pt-PT",
        "services": [
            "SEO Multilingue",
            "Localização de Websites",
            "Copywriting Multilingue",
            "Conteúdos Corporativos",
            "Consultoria em Comunicação Internacional",
            "Gestão de Reputação e Presença Digital",
        ],
        "quote_form_enabled": True,
        "qualification_fields": ["name", "company", "email", "service", "need"],
        "scheduling_link": SCHEDULING_LINK,
        "allowed_domains": ALLOWED_DOMAINS,
        "rules": (
            "Formal PT-PT ('você'). Mensagens curtas (1-2 frases). Uma pergunta por turno. "
            "SEO É serviço da Consenso Global — nunca negar. Quando pedirem tradução para "
            "'português' sem variante, PERGUNTAR qual variante. Usar exclusivamente o link "
            "Pipedrive oficial. Nunca partilhar informação da Consenso Plus, imóveis ou "
            "outros agentes."
        ),
        "system_prompt": SYSTEM_PROMPT,
        "knowledge": "",
        "default_language": "pt",
        "icebreakers": ICEBREAKERS,
        "welcome_message": WELCOME_MESSAGE,
        "api_provider": "openai",
        "api_key": "",
        "model_provider": "openai",
        "model_name": "gpt-4o-mini",
        "data_source_ids": [source_id],
        "tools": [{"key": "create_lead", "enabled": True}],
        "channels": {
            "webchat": {"enabled": True},
            "whatsapp": {"enabled": False},
            "telegram": {"enabled": False},
            "instagram": {"enabled": False},
            "messenger": {"enabled": False},
        },
        "email_config": {},
        "config": {
            "max_history": 24,
            "lead_capture_required": True,
        },
        "is_customized": False,
        "updated_at": now_iso(),
    }

    if existing_agent:
        # Preserve customizations (is_customized flag): only refresh core content
        if existing_agent.get("is_customized"):
            update_fields = {
                "scheduling_link": SCHEDULING_LINK,
                "allowed_domains": ALLOWED_DOMAINS,
                "formality": "formal",
                "default_pt_variant": "pt-PT",
                "services": agent_payload["services"],
                "quote_form_enabled": True,
                "qualification_fields": agent_payload["qualification_fields"],
                "data_source_ids": [source_id],
                "updated_at": now_iso(),
            }
            await db.agents.update_one({"id": existing_agent["id"]}, {"$set": update_fields})
            print(f"  · Agente Clara ATUALIZADO (safe/customized): {existing_agent['id'][:8]}…")
        else:
            await db.agents.update_one({"id": existing_agent["id"]}, {"$set": agent_payload})
            print(f"  · Agente Clara ATUALIZADO: {existing_agent['id'][:8]}…")
    else:
        agent_id = str(uuid.uuid4())
        agent_payload["id"] = agent_id
        agent_payload["created_at"] = now_iso()
        await db.agents.insert_one(agent_payload)
        print(f"  · Agente Clara CRIADO: {agent_id[:8]}…")


if __name__ == "__main__":
    asyncio.run(run())
