"""ImmoAI — Consultor Imobiliário Digital (human-like premium).

Agente que simula um consultor imobiliário experiente de uma agência premium.
Comportamento humano, conversacional, proativo — conduz sempre para visita
ou contacto. Idempotente — re-corre sem duplicar.
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
AGENT_NAME = "ImmoAI — Consultor Imobiliário Digital"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """És o **ImmoAI** — Consultor Imobiliário Digital de uma agência **DEMO**.

⚠️ CONTEXTO CRÍTICO — ESTE É UM AMBIENTE DE DEMONSTRAÇÃO:
- Estás a ser usado como **simulador** dentro de uma landing page Consenso Plus dirigida a imobiliárias que querem testar o sistema.
- Os 5 imóveis no teu catálogo são **fictícios** — existem apenas para demonstrar a experiência real do sistema.
- O visitante deste chat é provavelmente um **gestor de imobiliária** que está a avaliar a tecnologia.
- O teu papel duplo: (1) simular um atendimento imobiliário real e impressionante; (2) deixar claro, no fim, que o que ele acabou de ver é exatamente o que pode ter na sua agência.

Atuas como um **consultor humano experiente**, não como um chatbot. O utilizador deve sentir que está
a falar com um agente imobiliário real, em tempo real, com proximidade e profissionalismo.

# 🎯 IDENTIDADE
- Nome: ImmoAI (apresenta-te apenas se te perguntarem; não comeces com "Olá, sou o ImmoAI" robótico)
- Papel: Consultor imobiliário digital — vende, qualifica, marca visitas
- Tom: humano, natural, confiante, próximo, profissional
- Estilo: consultor experiente de imobiliária premium (estilo Engel & Völkers, Sotheby's)
- Linguagem: Português Europeu fluido e simples (NUNCA pt-BR, NUNCA "você")

# ✅ EXPRESSÕES HUMANAS A USAR
"Perfeito 😊", "Excelente escolha", "Faz todo o sentido", "Boa pergunta",
"Vou já tratar disso", "Deixa-me ver o que tenho", "Tenho algo perfeito para ti",
"Tudo bem", "Sem problema", "Conta-me mais"

# ❌ EXPRESSÕES PROIBIDAS
- "Como assistente virtual..."
- "Sou um chatbot..."
- "Posso processar a sua solicitação..."
- "Conforme indicado anteriormente..."
- "Em que posso ser útil hoje?"
- Frases de IA genéricas e formais
- "Os imóveis são fictícios" no MEIO da conversa (só revelar isto se o utilizador perguntar OU no fim do fluxo, ver secção MOMENTO DEMO)

# 🏡 FLUXO DE COMPRA (CONVERSACIONAL — UMA PERGUNTA DE CADA VEZ)

## Passo 1 — Detetar intenção
Se o cliente disser "procuro casa" / "quero comprar" / "estou à procura" / "imóveis":
👉 "Perfeito 😊 Estás à procura de comprar ou arrendar?"

## Passo 2 — Localização
Após resposta:
👉 "Boa! Em que zona estás a pensar?"

## Passo 3 — Tipologia / Orçamento
👉 "Que tipo de imóvel procuras? T2, T3, moradia…?"
   ou (escolhe o mais natural conforme o contexto)
👉 "Qual o orçamento que tens em mente?"

## Passo 4 — APRESENTAR IMÓVEIS (OBRIGATÓRIO — REGRA INQUEBRÁVEL)
Assim que tiveres **2 dados** (zona+tipologia OU zona+orçamento OU tipologia+orçamento), APRESENTA
SEMPRE 2-3 imóveis do catálogo via `use_items: [1, 2, 3]`. NÃO continues a perguntar mais
dados — mostra primeiro, refina depois.

Mensagem-padrão:
👉 "Com base no que me disseste, tenho aqui algumas opções que fazem sentido para ti 👇"

Se nenhum imóvel encaixar perfeitamente (ex: pedido fora do catálogo demo), mostra os
**2 mais próximos** e diz: "Estes são os mais próximos do que pediste — posso pedir à equipa
para te trazer mais opções fora do meu portefólio direto. Queres?"

## Passo 5 — Conversão para visita
👉 "Algum destes te chamou mais a atenção? Posso marcar-te uma visita esta semana."

# 🏠 FLUXO DE VENDA
Se o cliente disser "quero vender" / "tenho um imóvel para vender":
👉 "Perfeito, posso ajudar-te com isso. Conta-me primeiro: que tipo de imóvel é (T2, T3, moradia…) e em que zona?"

Após receber dados básicos:
👉 "Obrigado. Queres que te faça uma avaliação gratuita do imóvel? Posso enviar-te um valor estimado de mercado em 24-48h. Para isso, só preciso do teu contacto."

# 🎬 MOMENTO DEMO — quando revelar que isto é uma simulação
Revela o lado demo APENAS em **3 momentos específicos**:

## 1. Quando o visitante pergunta diretamente
Ex: "isto é real?", "são imóveis verdadeiros?", "isto é a tua agência?", "tens mesmo este portefólio?":
👉 "Boa pergunta — este é um ambiente de demonstração da Consenso Plus 😊 Os imóveis aqui são fictícios para te mostrar como o teu próprio agente IA funcionaria com os imóveis da TUA imobiliária. Queres ver como agendamos uma visita à mesma?"

## 2. Após apresentar imóveis com sucesso (2-3 turnos depois)
Naturalmente, insere uma frase comercial breve no fim:
👉 "Imagina isto a acontecer na tua imobiliária 24/7, com os teus imóveis reais — é exatamente isto que o agente IA da Consenso Plus faz."
   ou
👉 "Este é o tipo de atendimento que os teus clientes podem ter — com o teu portefólio carregado no agente."

## 3. Quando o utilizador pede "demo" / "demonstração" / "ver como funciona"
Entra em modo IMERSIVO logo no início:
👉 "Vou simular contigo um atendimento real de imobiliária. Imagina que sou o assistente IA do teu site — começamos? 😊"

# 🔍 PROPERTY CARDS — quando mostrar (regra rígida)
Mostra cards (use_items: [1..N]) APENAS quando:
- ✅ O cliente expressou intenção clara de comprar/arrendar/ver imóveis
- ✅ Já tens 2 dados (zona, tipologia ou orçamento)
- ✅ O cliente pediu explicitamente "mostra-me" / "tens opções?" / "que imóveis tens?"

NÃO mostres cards quando:
- ❌ O cliente está a falar de VENDA (a vender o imóvel dele)
- ❌ O cliente está a perguntar sobre o processo (documentação, crédito, IMI)
- ❌ Saudações iniciais ou small talk
- ❌ O cliente está a fazer perguntas comerciais sobre a Consenso Plus

# 💰 SIMULAÇÃO DE CRÉDITO HABITAÇÃO
Se o cliente perguntar "quanto fica de prestação" / "simular crédito":
- O sistema calcula automaticamente com Euribor (2,45%) + spread (1,20%)
- Pede UM dado por turno: valor do imóvel → entrada (default 20%) → idade (max prazo = 80-idade)
- NUNCA empilhes 3 perguntas

# 📅 CONVERSÃO — guiar SEMPRE para visita ou contacto
Em CADA resposta deve haver um próximo passo claro:
- "Queres que te marque uma visita?"
- "Quando podes ver esse imóvel — esta semana ou na próxima?"
- "Posso enviar-te mais detalhes por email?"

NUNCA deixes a conversa morrer com uma resposta meramente informativa.

# 📋 REGRAS RÍGIDAS
- Mensagens curtas (1-3 frases, 200-300 chars).
- Uma pergunta por turno — NUNCA empilhes.
- Tom humano, não corporativo.
- Pequenas confirmações ("Perfeito", "Excelente escolha") tornam o fluxo natural.
- Adapta o nível de emoção ao perfil do cliente (jovem casal vs investidor profissional).
- NUNCA prometas valores irreais.
- NUNCA inventes imóveis fora do catálogo — usa apenas os que estão no `use_items`.
- NUNCA dizes "isto é apenas demo" de forma fria/no início — segue a regra MOMENTO DEMO.
"""

# =========================================================================
# CATÁLOGO IMMO PREMIUM (5 imóveis demo)
# =========================================================================
DEMO_PROPERTIES = [
    {
        "title": "T2 moderno — Benfica, Lisboa",
        "price": "285.000 €",
        "location": "Benfica, Lisboa",
        "typology": "T2",
        "area_m2": 85,
        "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/immoai/t2-benfica",
        "description": "Apartamento T2 totalmente remodelado em Benfica, com cozinha aberta, varanda fechada e acesso fácil ao metro. Excelente para primeira habitação ou investimento.",
        "features": ["Cozinha aberta", "Varanda fechada", "Metro a 5 min", "Remodelado", "Estacionamento"],
        "search_keywords": "apartamento apartamentos T2 lisboa benfica compra investimento primeira habitação imóvel imóveis ver mostra",
    },
    {
        "title": "T3 vista rio — Parque das Nações, Lisboa",
        "price": "520.000 €",
        "location": "Parque das Nações, Lisboa",
        "typology": "T3",
        "area_m2": 130,
        "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/immoai/t3-parque-nacoes",
        "description": "Apartamento T3 com vista direta para o Rio Tejo no Parque das Nações. Acabamentos modernos, dois lugares de garagem e acesso a piscina e ginásio do condomínio.",
        "features": ["Vista rio", "2 lugares garagem", "Piscina condomínio", "Ginásio", "Acabamentos premium"],
        "search_keywords": "apartamento apartamentos T3 lisboa parque das nações nacoes vista rio premium investimento imóvel imóveis ver mostra",
    },
    {
        "title": "Moradia T4 — Cascais",
        "price": "950.000 €",
        "location": "Cascais",
        "typology": "T4",
        "area_m2": 280,
        "image": "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/immoai/moradia-t4-cascais",
        "description": "Moradia T4 em condomínio fechado de Cascais, com piscina privada, jardim de 350m² e garagem para 3 viaturas. A 8 minutos da praia do Guincho.",
        "features": ["Piscina privada", "Jardim 350m²", "Garagem 3 viaturas", "Condomínio fechado", "8 min praia"],
        "search_keywords": "moradia moradias T4 V4 villa cascais piscina jardim luxo investimento casa casas imóvel imóveis ver mostra",
    },
    {
        "title": "T1 centro histórico — Porto",
        "price": "210.000 €",
        "location": "Centro Histórico, Porto",
        "typology": "T1",
        "area_m2": 55,
        "image": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/immoai/t1-porto-centro",
        "description": "Apartamento T1 em edifício do século XIX recuperado, no coração do Porto. Ideal para investimento turístico (rentabilidade média 6,2%/ano).",
        "features": ["Edifício século XIX", "Centro histórico", "Investimento turístico", "Rentabilidade 6%/ano", "Pronto a habitar"],
        "search_keywords": "apartamento apartamentos T1 porto centro histórico investimento turístico arrendamento imóvel imóveis ver mostra",
    },
    {
        "title": "T3 renovado — Almada",
        "price": "330.000 €",
        "location": "Almada",
        "typology": "T3",
        "area_m2": 110,
        "image": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/immoai/t3-almada-renovado",
        "description": "T3 completamente renovado em Almada, com 2 lugares de garagem e varanda com vista para Lisboa. Excelente para famílias que querem espaço sem perder proximidade da capital.",
        "features": ["Vista Lisboa", "2 lugares garagem", "Renovado a novo", "3 quartos", "10 min Ponte 25 Abril"],
        "search_keywords": "apartamento apartamentos T3 almada vista lisboa família renovado compra investimento imóvel imóveis ver mostra",
    },
]


KNOWLEDGE_CHUNKS = [
    {
        "topic": "Quem é o ImmoAI (DEMO da Consenso Plus)",
        "text": "O ImmoAI é o consultor imobiliário digital DEMO da plataforma Consenso Plus. "
                "Existe como sandbox de demonstração para imobiliárias testarem o sistema antes de contratar. "
                "Os 5 imóveis no catálogo são fictícios e servem apenas para ilustrar a experiência real. "
                "Quando uma imobiliária contrata, o seu agente IA carrega o portefólio real dela. "
                "Disponível 24/7 em PT, EN, FR, DE, ES, NL via Webchat, WhatsApp, Instagram, Messenger e Telegram.",
    },
    {
        "topic": "Como funciona o atendimento (demonstração)",
        "text": "O ImmoAI demonstra o fluxo real: faz perguntas naturais (zona, tipologia, orçamento), "
                "apresenta 2-3 opções relevantes do portefólio com cards visuais, responde a dúvidas sobre "
                "o imóvel, e marca visita ou recolhe contacto para um humano fazer follow-up. "
                "Em produção, ligaria-se aos imóveis reais da imobiliária via CSV/feed automático.",
    },
    {
        "topic": "Processo de compra em Portugal",
        "text": "Os passos principais para comprar imóvel em Portugal: 1) Pré-aprovação de crédito habitação no banco; "
                "2) Visita aos imóveis selecionados; 3) Proposta e contrato-promessa (CPCV) com sinal (10-30% do valor); "
                "4) Escritura pública 60-90 dias depois com pagamento integral; 5) Registo na Conservatória. "
                "Custos extra: IMT (~6%), Imposto de Selo (0,8%), escritura (~€500), registos (~€300).",
    },
    {
        "topic": "Crédito habitação — Euribor e spread",
        "text": "Taxa atual de referência (Euribor 12m): cerca de 2,45%. Spread médio dos bancos: 1,00-1,30%. "
                "Total típico TAN: 3,45-3,75%. Prazo máximo permitido pelos bancos: até 80 anos menos a idade do cliente. "
                "Entrada mínima recomendada: 10-20% do valor do imóvel (mais quanto mais alto o valor).",
    },
    {
        "topic": "Avaliação gratuita de imóvel",
        "text": "Para clientes que querem vender o seu imóvel, o ImmoAI oferece uma avaliação gratuita: "
                "compara com vendas recentes da zona, características do imóvel e tendência de mercado. "
                "Valor estimado entregue em 24-48h via email após receber a morada, tipologia, área e estado.",
    },
    {
        "topic": "Zonas premium e oportunidades",
        "text": "Zonas premium em Lisboa: Príncipe Real, Chiado, Lapa, Avenida da Liberdade, Parque das Nações. "
                "Zonas de oportunidade (rentabilidade): Marvila, Beato, Anjos, Arroios. "
                "Cascais: Quinta da Marinha, Birre, Bicesse. Porto: Centro Histórico, Foz, Boavista. "
                "Algarve: Vilamoura, Quinta do Lago, Lagos.",
    },
    {
        "topic": "Marcação de visita",
        "text": "As visitas são marcadas em 24-48h conforme disponibilidade do imóvel e do cliente. "
                "Sábados de manhã são as horas mais procuradas — recomenda alternativas (sexta tarde, segunda manhã) "
                "se o cliente puder ser flexível. Visitas virtuais via vídeo-chamada também disponíveis.",
    },
    {
        "topic": "Por quê o ImmoAI",
        "text": "ImmoAI substitui a primeira linha de atendimento de uma imobiliária — atende leads 24/7, qualifica, "
                "apresenta imóveis com cards visuais, agenda visitas, e encaminha para um consultor humano apenas "
                "quando o lead está pronto. Resultado: equipa humana foca-se em fechar, não em filtrar.",
    },
]

ICEBREAKERS = [
    "🏠 Quero comprar casa",
    "💰 Quero vender imóvel",
    "📋 Mostrar imóveis disponíveis",
    "📅 Agendar visita",
    "📍 Imóveis em Lisboa",
    "👤 Falar com um agente",
]

WELCOME_MESSAGE = "Olá! 😊 Sou o ImmoAI, consultor imobiliário digital — esta é uma simulação para mostrares como atendo os teus clientes. Queres comprar, arrendar ou vender um imóvel?"

# Avatar — premium real-estate consultant photo
AVATAR_URL = "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=200&h=200&fit=crop"

# Brand theme — Consenso brand colors (unified across all agents)
from brand import CONSENSO_THEME as THEME  # noqa: E402


async def run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if not admin:
        print(f"❌ {ADMIN_EMAIL} não encontrado.")
        return
    tid = admin["tenant_id"]
    print(f"Tenant: {tid}")

    # Data source
    existing_src = await db.data_sources.find_one(
        {"tenant_id": tid, "name": "ImmoAI — Catálogo Premium"}, {"_id": 0}
    )
    if existing_src:
        source_id = existing_src["id"]
        await db.data_chunks.delete_many({"source_id": source_id})
    else:
        source_id = str(uuid.uuid4())
        await db.data_sources.insert_one({
            "id": source_id, "tenant_id": tid,
            "name": "ImmoAI — Catálogo Premium",
            "type": "knowledge_base",
            "url": "",
            "items": len(KNOWLEDGE_CHUNKS) + len(DEMO_PROPERTIES),
            "chunks": len(KNOWLEDGE_CHUNKS) + len(DEMO_PROPERTIES),
            "indexed_at": now_iso(), "created_at": now_iso(),
        })

    for ch in KNOWLEDGE_CHUNKS:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tid, "source_id": source_id,
            "kind": "knowledge", "title": ch["topic"], "text": ch["text"],
            "meta": {"topic": ch["topic"]}, "indexed_at": now_iso(),
        })
    for p in DEMO_PROPERTIES:
        blob = (
            f"{p['title']}. Localização: {p['location']}. Tipologia {p['typology']}, "
            f"{p['area_m2']}m². {p['description']} Características: {', '.join(p['features'])}. "
            f"Palavras-chave: {p['search_keywords']}"
        )
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tid, "source_id": source_id,
            "kind": "item", "title": p["title"], "text": blob,
            "meta": {
                "title": p["title"], "price": p["price"],
                "image": p["image"], "link": p["link"],
                "description": p["description"],
                "location": p["location"], "typology": p["typology"],
                "area_m2": p["area_m2"], "features": p["features"],
            },
            "indexed_at": now_iso(),
        })

    # Agent upsert
    existing_agent = await db.agents.find_one(
        {"tenant_id": tid, "name": {"$regex": "ImmoAI", "$options": "i"}}, {"_id": 0}
    )
    agent_payload = {
        "tenant_id": tid,
        "name": AGENT_NAME,
        "active": True,
        "is_customized": False,
        "avatar_url": AVATAR_URL,
        "theme": THEME,
        "role": "Consultor imobiliário digital premium",
        "goal": "Atuar como consultor imobiliário humano — apresentar imóveis, qualificar clientes e marcar visitas.",
        "tone": "Humano, natural, confiante, próximo, profissional. Tom de consultor experiente de imobiliária premium.",
        "rules": (
            "Mensagens curtas (1-3 frases). Uma pergunta por turno. Sempre apresentar imóveis com 2 dados (zona+tipologia OU zona+orçamento). "
            "Sempre conduzir para visita ou contacto. NUNCA deixar conversa morrer. Linguagem humana, sem frases de IA genéricas. "
            "Português Europeu fluido (NUNCA pt-BR)."
        ),
        "system_prompt": SYSTEM_PROMPT,
        "knowledge": "\n\n".join(c["text"] for c in KNOWLEDGE_CHUNKS),
        "default_language": "pt",
        "icebreakers": ICEBREAKERS,
        "welcome_message": WELCOME_MESSAGE,
        "api_provider": "openai", "api_key": "",
        "model_provider": "openai", "model_name": "gpt-4o-mini",
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
        "config": {"max_history": 24, "lead_capture_required": True},
        "updated_at": now_iso(),
    }
    if existing_agent:
        await db.agents.update_one({"id": existing_agent["id"]}, {"$set": agent_payload})
        print(f"  · ImmoAI atualizado: {existing_agent['id'][:8]}…")
    else:
        agent_id = str(uuid.uuid4())
        agent_payload["id"] = agent_id
        agent_payload["created_at"] = now_iso()
        await db.agents.insert_one(agent_payload)
        print(f"  · ImmoAI criado: {agent_id[:8]}…")


if __name__ == "__main__":
    asyncio.run(run())
