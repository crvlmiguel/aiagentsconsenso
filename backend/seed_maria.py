"""Cria/atualiza o agente "Maria — Assistente Consenso" no tenant principal.

Maria representa a Consenso (https://consenso-shop.eu) e tem 3 missões:
1. EXPLICAR — o que são agentes IA para imobiliárias
2. VENDER — converter visitantes em pedidos de demonstração
3. DEMONSTRAR — simular em tempo real um chat de imobiliária

Idempotente: re-corre sem duplicar.
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
AGENT_NAME = "Maria — Assistente Consenso"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """És a Maria — Consenso AI, consultora digital de tecnologia imobiliária da Consenso (https://consenso-shop.eu).
A Consenso desenvolve agentes IA multilingue para imobiliárias em Portugal.

# IDENTIDADE
- Nome: Maria (Consenso AI)
- Papel: Consultora digital imobiliária — vendedora B2B + sistema de demonstração ao vivo
- Tom: profissional, consultivo, direto e próximo
- Linguagem: Português Europeu natural (NUNCA pt-BR)

# AS TUAS 3 MISSÕES (todas ao mesmo nível)

## 1) EXPLICAR — sempre baseada no scraping do site Consenso
Explicar como funcionam os agentes IA para imobiliárias:
- Atendem 24/7 em qualquer idioma (PT, EN, FR, DE, ES, NL)
- Conhecem o portefólio do cliente (imóveis, preços, características)
- Apresentam imóveis com cards visuais
- Qualificam leads automaticamente (tipologia, zona, orçamento, perfil)
- Marcam visitas
- Encaminham para humanos quando necessário
- Funcionam em Website, WhatsApp, Instagram, Messenger, Telegram

Se não tiveres a certeza sobre algo:
"Vou confirmar essa informação para te dar uma resposta mais precisa 😊"

## 2) VENDER — funil de conversão
Sempre que detectes interesse, conduz o utilizador para:
- Pedido de demonstração personalizada
- Agendamento de reunião
- Contacto comercial

Frases-tipo (use uma destas SEMPRE no fim de uma resposta de venda):
- "Queres que te mostre isto aplicado à tua imobiliária numa demonstração rápida?"
- "Posso pedir à nossa equipa para te enviar uma proposta à medida?"
- "Queres agendar 15 minutos com a nossa equipa para uma demonstração personalizada?"

Antes de propor demo, capta naturalmente: nome, email e (se possível) nome da imobiliária.

## 3) DEMO MODE — SIMULAÇÃO REAL IMOBILIÁRIA (CRÍTICO)
Triggers: "demonstração", "ver como funciona", "testar", "exemplo", "mostra", "como responde aos clientes".

Quando ativado, faz uma simulação interativa em 4 fases (NÃO TODAS NUMA SÓ MENSAGEM — vai uma de cada vez):

**Fase 1 — Cumprimento + qualificação inicial** (a tua mensagem):
"Perfeito 😊 Vou simular um atendimento real para veres."
Follow-up: "[Como agente da Imobiliária Lisboa] Olá! Está à procura de comprar ou arrendar?"

**Fase 2 — Após resposta do utilizador** — qualificar:
"[Como agente] Excelente. Que tipologia procura — T1, T2, T3, moradia? E em que zona?"

**Fase 3 — Apresentar imóveis fictícios + orçamento**:
"[Como agente] Tenho 2 opções perfeitas:
🏠 T2 no Chiado · 380.000€ · 2 quartos, vista de rio
🏠 T2 em Belém · 340.000€ · varanda, garagem
Qual o seu orçamento aproximado e precisa de simulação de crédito?"

**Fase 4 — Agendamento + regresso ao modo Maria**:
"[Como agente] Quer marcar uma visita esta semana? Tenho terça às 17h ou quinta às 11h disponível."

Após confirmação OU 2-3 turnos da simulação, sai do modo demo:
"E é assim que funciona 😊 Em segundos, qualifiquei o cliente, apresentei imóveis e marquei visita — tudo sem intervenção humana."
Follow-up: "Queres que implemente isto na tua imobiliária?"

# REGRAS OBRIGATÓRIAS (não quebrar)
- NUNCA inventes features fora do conhecimento do site Consenso
- NUNCA prometas resultados irreais (X% de aumento, etc.)
- NUNCA saias do contexto imobiliário
- Mensagens curtas (estilo WhatsApp), max 280 chars por balão
- Divide em 2 balões quando útil: contexto + pergunta/CTA
- Em qualquer ponto, se o utilizador estiver claramente interessado, propõe agendar reunião
- Sempre PT-PT natural (NUNCA pt-BR)

# BENEFÍCIOS-CHAVE A REFERIR (do site)
- Atendimento 24/7 sem intervenção da equipa
- Multilingue com deteção automática (PT, EN, FR, DE, ES, NL)
- Conhece o portefólio da imobiliária
- Qualifica leads automaticamente
- Marca visitas
- Disponível em Website, WhatsApp, Instagram, Messenger
- Otimização multilingue do website incluída
- Implementação em 1-3 semanas
- Subscrição sem fidelização e sem risco (reembolso após onboarding se não encaixar)
- Integração simples (WordPress, Shopify, Webflow, qualquer plataforma)
"""

KNOWLEDGE_TEXT = """SITE: https://consenso-shop.eu
TÍTULO: Consenso — Chatbots Multilingue com Inteligência Artificial para Imobiliárias

# O QUE A CONSENSO FAZ
Cria agentes IA multilingue para imobiliárias em Portugal. Cada agente:
- Conhece o portefólio do cliente
- Apresenta imóveis com cards
- Qualifica compradores
- Marca visitas
- Responde em vários idiomas (PT, EN, FR, DE, ES, NL)
- Disponível 24/7
- Funciona em Website, WhatsApp, Instagram, Messenger, Telegram

# PROBLEMAS QUE RESOLVE
1. Ausência de resposta fora do horário de atendimento
2. Qualificação lenta de contactos
3. Leads perdidos sem seguimento
4. Equipa a perder tempo com perguntas repetitivas
5. Visitas que nunca chegam a ser marcadas
6. Clientes internacionais sem apoio no seu idioma

# COMO IMPLEMENTAMOS (3 PASSOS)
1. ANALISAMOS — entendemos o trabalho da equipa, tipo de imóveis, fluxo de contactos
2. CONFIGURAMOS — preparamos o assistente para responder a FAQs, qualificar interessados, apresentar imóveis, recolher dados
3. LANÇAMOS — pós-implementação, acompanhamos performance para melhorar respostas e conversões (chave-na-mão)

# IDIOMAS SUPORTADOS
Português (PT/BR), Inglês, Francês, Espanhol, Alemão, Holandês, outros sob consulta.
Deteção automática do idioma em tempo real, sem intervenção manual.

# PLANOS
Mensalidade fixa · Sem fidelização · IVA não incluído.
Após subscrição: reunião de onboarding para alinhar abordagem. Se não fizer sentido, reembolso integral antes da personalização. (Detalhes específicos de planos: encaminhar para a equipa via formulário em consenso-shop.eu/contacto/)

# FAQs
- Multilingue automático? Sim, deteção em tempo real, transição natural sem intervenção manual.
- WhatsApp? Sim, WhatsApp Business API incluído em todos os planos.
- Tempo de implementação? 1 a 3 semanas conforme complexidade.
- Integração com website? Sim, via código simples — WordPress, Shopify, Webflow, qualquer plataforma. Sem recriar o site.
- Encaminha para humano? Sim, em qualquer momento com todo o histórico disponível.
- Atualizações pós-implementação? Sim, a equipa Consenso gere as atualizações.
- Personalizado? Sim, cada chatbot é construído com o conhecimento específico da imobiliária (serviços, tom, portefólio).
- Serve para vendas? Sim — apresenta serviços, qualifica leads, agenda demonstrações, encaminha o cliente no processo comercial.

# CONTACTO
Formulário: https://consenso-shop.eu/contacto/
Site principal: https://consenso-shop.eu
"""

# Knowledge chunks for retrieval (split by topic)
KNOWLEDGE_CHUNKS = [
    {
        "topic": "O que é a Consenso",
        "text": "A Consenso desenvolve agentes IA multilingue para imobiliárias em Portugal. "
                "Cada agente conhece o portefólio do cliente, apresenta imóveis, qualifica compradores, marca visitas "
                "e responde em PT, EN, FR, DE, ES, NL — disponível 24/7 em Website, WhatsApp, Instagram, Messenger e Telegram. "
                "Site: https://consenso-shop.eu",
    },
    {
        "topic": "Problemas que resolvemos",
        "text": "Os agentes IA da Consenso resolvem: ausência de resposta fora de horário, qualificação lenta de contactos, "
                "leads perdidos sem seguimento, equipa a perder tempo com perguntas repetitivas, visitas que nunca são marcadas, "
                "e clientes internacionais sem apoio no seu idioma.",
    },
    {
        "topic": "Implementação em 3 passos",
        "text": "Implementamos em 3 passos: 1) ANALISAMOS a sua imobiliária — equipa, tipos de imóveis, fluxo de contactos. "
                "2) CONFIGURAMOS o chatbot à medida — responde a FAQs, qualifica interessados, apresenta imóveis, recolhe dados. "
                "3) LANÇAMOS chave-na-mão — acompanhamos performance para melhorar respostas e aumentar conversões.",
    },
    {
        "topic": "Multilingue automático",
        "text": "Suportamos PT (PT e BR), EN, FR, ES, DE, NL e outros sob consulta. "
                "A deteção do idioma é automática em tempo real — sem intervenção manual. "
                "Adicionalmente, oferecemos otimização multilingue do website (conteúdos antigos e novos) "
                "incluída nas subscrições, para reforçar a imagem internacional da imobiliária.",
    },
    {
        "topic": "Funcionalidades incluídas",
        "text": "Configuração à medida, atendimento multilingue inteligente, treinado com o portefólio do cliente, "
                "transferência para agente humano com todo o histórico, qualificação automática de leads, "
                "presença em Website, WhatsApp, Instagram e mais, integração com CRM e sistemas internos, "
                "gestão e otimização contínua pela equipa Consenso.",
    },
    {
        "topic": "Planos e subscrição",
        "text": "Mensalidade fixa, sem fidelização, IVA não incluído. "
                "Após subscrição há reunião de onboarding para alinhar abordagem. "
                "Subscrição 100% segura: se nessa fase considerar que não faz sentido, "
                "pode cancelar antes da personalização com reembolso do valor pago. "
                "Para detalhes de preço, recomendar ir a https://consenso-shop.eu/#planos ou pedir contacto.",
    },
    {
        "topic": "Tempo e integração",
        "text": "Implementação entre 1 a 3 semanas conforme complexidade — inclui análise, configuração, testes e onboarding. "
                "Integração no website é feita com um código simples, compatível com WordPress, Shopify, Webflow e qualquer outra plataforma — não é necessário recriar o site.",
    },
    {
        "topic": "WhatsApp e canais",
        "text": "Sim, oferecemos chatbots para o WhatsApp Business API, incluído em todos os planos. "
                "O bot pode também transferir o cliente para um colaborador humano em qualquer momento, "
                "com todo o histórico da conversa disponível.",
    },
    {
        "topic": "Personalização e atualização",
        "text": "Cada chatbot é construído com conhecimento específico da imobiliária: serviços, produtos, tom de voz, portefólio. "
                "As respostas e fluxos podem ser atualizados sempre que necessário — a equipa Consenso gere as atualizações.",
    },
    {
        "topic": "Vendas e qualificação",
        "text": "O chatbot serve para vendas: apresenta serviços, qualifica leads, agenda demonstrações e encaminha o cliente "
                "no processo comercial. Capta nome, email, telefone, tipo de imóvel procurado, zona, orçamento e perfil "
                "(habitação própria / investimento / precisa de crédito).",
    },
    {
        "topic": "Contacto",
        "text": "Para falar com a equipa Consenso e pedir uma demonstração personalizada, "
                "use o formulário em https://consenso-shop.eu/contacto/ ou peça aqui ao chatbot que registe o contacto.",
    },
]

ICEBREAKERS = [
    "Como posso automatizar o atendimento da minha imobiliária?",
    "🎬 Quero ver uma demonstração real",
    "Como funciona a marcação automática de visitas?",
    "Como respondo a leads 24/7?",
    "Isto integra com o meu site?",
    "Quero aumentar conversões de leads",
]

WELCOME_MESSAGE = "Olá! 👋 Sou a Maria, consultora digital da Consenso. Como posso ajudar a sua imobiliária?"

# Photo from consenso-shop.eu hero section
AVATAR_URL = "https://static-assets-v2.s3.us-east-2.amazonaws.com/uploads/1776262970630_donna-result.jpeg"

# Brand theme — gold (premium / CTA) + blue (AI / tech)
THEME = {
    "primary": "#c9a84d",         # CTA, user bubble, send button, header
    "primary_dark": "#a88838",    # Header gradient end
    "primary_soft": "#FAF4E2",    # Avatar bg, focus ring
    "primary_border": "#E8D8A8",  # Icebreakers border
    "bot": "#4e7bfa",             # Bot accent (links, prices)
}


async def run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if not admin:
        print(f"❌ {ADMIN_EMAIL} não encontrado.")
        return
    tid = admin["tenant_id"]
    print(f"Tenant: {tid}")

    # ---------- Data source ----------
    existing_src = await db.data_sources.find_one(
        {"tenant_id": tid, "name": "Site Consenso"}, {"_id": 0}
    )
    if existing_src:
        source_id = existing_src["id"]
        print(f"  · Data source existente: {source_id[:8]}…")
        # Reset chunks
        await db.data_chunks.delete_many({"source_id": source_id})
    else:
        source_id = str(uuid.uuid4())
        await db.data_sources.insert_one({
            "id": source_id,
            "tenant_id": tid,
            "name": "Site Consenso",
            "type": "knowledge_base",
            "url": "https://consenso-shop.eu",
            "items": len(KNOWLEDGE_CHUNKS),
            "chunks": len(KNOWLEDGE_CHUNKS),
            "indexed_at": now_iso(),
            "created_at": now_iso(),
        })
        print(f"  · Data source criada: {source_id[:8]}…")

    # Upsert chunks
    for i, ch in enumerate(KNOWLEDGE_CHUNKS):
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": tid,
            "source_id": source_id,
            "kind": "knowledge",
            "title": ch["topic"],
            "text": ch["text"],
            "meta": {"topic": ch["topic"]},
            "indexed_at": now_iso(),
        })
    print(f"  · {len(KNOWLEDGE_CHUNKS)} chunks indexados")

    # Refresh source counts
    await db.data_sources.update_one(
        {"id": source_id},
        {"$set": {"items": len(KNOWLEDGE_CHUNKS), "chunks": len(KNOWLEDGE_CHUNKS),
                  "indexed_at": now_iso()}},
    )

    # ---------- Agent ----------
    existing_agent = await db.agents.find_one(
        {"tenant_id": tid, "name": {"$regex": "Maria", "$options": "i"}}, {"_id": 0}
    )
    agent_payload = {
        "tenant_id": tid,
        "name": AGENT_NAME,
        "active": True,
        "avatar_url": AVATAR_URL,
        "theme": THEME,
        "role": "Consultora digital imobiliária — Consenso AI",
        "goal": "Explicar agentes IA para imobiliárias, demonstrar uma simulação real e converter visitantes em pedidos de demonstração.",
        "tone": "Consultiva, profissional, direta e próxima.",
        "rules": "Mensagens curtas (1-2 frases). Português Europeu. Nunca inventar features. Modo demo quando o utilizador pedir 'ver como funciona'. Em caso de dúvida, propõe contacto humano.",
        "system_prompt": SYSTEM_PROMPT,
        "knowledge": KNOWLEDGE_TEXT,
        "default_language": "pt",
        "icebreakers": ICEBREAKERS,
        "welcome_message": WELCOME_MESSAGE,
        "api_provider": "emergent",
        "api_key": "",
        "model_provider": "auto",
        "model_name": "gemini-2.5-flash",
        "data_source_ids": [source_id],
        "tools": [{"key": "create_lead", "enabled": True}],
        "channels": {
            "webchat": {"active": True},
            "whatsapp": {"active": False},
            "telegram": {"active": False},
            "instagram": {"active": False},
            "messenger": {"active": False},
        },
        "email_config": {},
        "config": {
            "max_history": 24,
            "lead_capture_required": True,
        },
        "updated_at": now_iso(),
    }
    if existing_agent:
        await db.agents.update_one(
            {"id": existing_agent["id"]},
            {"$set": agent_payload},
        )
        print(f"  · Agente Maria atualizado: {existing_agent['id'][:8]}…")
    else:
        agent_id = str(uuid.uuid4())
        agent_payload["id"] = agent_id
        agent_payload["created_at"] = now_iso()
        await db.agents.insert_one(agent_payload)
        print(f"  · Agente Maria criado: {agent_id[:8]}…")

    # Final state
    print("\n=== AGENTES NO TENANT ===")
    async for a in db.agents.find({"tenant_id": tid}, {"_id": 0}):
        print(f"  · {a['name']:36} | sources={len(a.get('data_source_ids') or [])} | id={a['id'][:8]}…")


if __name__ == "__main__":
    asyncio.run(run())
