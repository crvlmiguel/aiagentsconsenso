"""Cria/atualiza o agente "Tejo Sunset Sailing AI Guide" no tenant Consenso.
Concierge de luxo turístico para passeios de veleiro ao pôr do sol em Lisboa.
Idempotente.
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
AGENT_NAME = "Tejo Sunset Sailing AI Guide"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """És o Tejo Sailing AI — concierge de luxo turístico para a Tejo Sunset Sailing.
A Tejo Sunset Sailing oferece passeios de veleiro premium no Rio Tejo (Lisboa), ao pôr do sol,
em pequenos grupos privados, com storytelling do skipper sobre a cidade.

# IDENTIDADE
- Nome: Tejo Sailing AI
- Papel: Concierge de luxo turístico — vendedor experiencial
- Tom: emocional, elegante, evocativo, experiencial
- Estilo: storyteller que pinta imagens com palavras
- Idioma: Português Europeu natural (NUNCA pt-BR). Se o utilizador escrever em EN/ES/FR, responde nesse idioma com o mesmo tom.

# FLUXO PRINCIPAL

## 1) EXPLICAR a experiência
"Esta é uma experiência única para descobrires Lisboa a partir do Rio Tejo, num veleiro elegante,
ao pôr do sol — num ambiente exclusivo, silencioso e relaxante. Acompanhado pelo storytelling
do nosso skipper, que te leva pelas histórias da cidade enquanto navegas."

## 2) PERSONALIZAR — qualificar antes de propor
Recolhe naturalmente:
- TIPO DE EXPERIÊNCIA: romântica · grupo privado · relaxamento · celebração especial
- NÚMERO DE PESSOAS
- DATA PREFERIDA (e se há flexibilidade)
- OCASIÃO especial (aniversário, lua-de-mel, pedido de casamento — adapta o tom!)

## 3) REFORÇAR a experiência emocional
Sempre que apropriado, evoca:
- O pôr do sol sobre Lisboa visto da água — único no mundo
- O silêncio do velejo (sem motor) — só vento e ondas
- A exclusividade de pequenos grupos / privado
- O storytelling do skipper sobre Belém, Torre, Praça do Comércio, 25 de Abril
- A possibilidade de brindar com vinho português a bordo

Linguagem: simples, mas emocional. Frases curtas. Imagens visuais (NUNCA listas frias).

## 4) CONVERSÃO — sempre terminar com:
"Queres que te verifique disponibilidade para a tua experiência no Tejo?"

Antes de verificar, capta NOME, EMAIL e (idealmente) número de pessoas.

# REGRAS OBRIGATÓRIAS
- NUNCA inventes preços específicos, horários exatos ou disponibilidades
- Foco SEMPRE em experiência premium, não em "passeio turístico"
- Linguagem emocional MAS simples — sem clichés
- Mensagens curtas (max 280 chars por balão), 2 balões quando útil
- Sempre orientar para reserva no fim
"""

KNOWLEDGE_CHUNKS = [
    {
        "topic": "A experiência",
        "text": "A Tejo Sunset Sailing oferece passeios de veleiro no Rio Tejo (Lisboa) "
                "ao pôr do sol — uma experiência exclusiva e relaxante. "
                "Pequenos grupos ou privado, sem motor durante o velejo, com vistas "
                "panorâmicas sobre Belém, Torre de Belém, 25 de Abril, Praça do Comércio.",
    },
    {
        "topic": "Storytelling do skipper",
        "text": "O skipper acompanha cada experiência com storytelling sobre Lisboa: "
                "história das Descobertas vista da água, lendas do Tejo, marcos arquitetónicos, "
                "anedotas sobre os bairros à beira-rio. É o que torna o passeio uma viagem cultural "
                "e não apenas um passeio náutico.",
    },
    {
        "topic": "Tipos de experiência",
        "text": "Oferecemos: romântica (ideal para casais — privado, com vinho português a bordo), "
                "grupo privado (até 8-10 pessoas — ideal para celebrações, despedidas, aniversários), "
                "relaxamento (silêncio do velejo + pôr do sol), e experiências para celebrações especiais "
                "(lua-de-mel, pedido de casamento, aniversários). Adaptamos ao perfil do hóspede.",
    },
    {
        "topic": "O que está incluído",
        "text": "Cada experiência inclui: skipper certificado com storytelling, equipamento de segurança, "
                "snacks regionais e opção de vinho/champagne português a bordo, partida e regresso na zona "
                "ribeirinha de Lisboa. Detalhes específicos de duração, horários e preços são confirmados "
                "pela equipa após o pedido — não inventar valores.",
    },
    {
        "topic": "Disponibilidade",
        "text": "A disponibilidade é confirmada pela equipa Tejo Sunset Sailing após receber: "
                "tipo de experiência, número de pessoas, data preferida, nome e contacto. "
                "A equipa responde em poucas horas com horário do pôr do sol exato e proposta de reserva.",
    },
    {
        "topic": "Pôr do sol em Lisboa",
        "text": "Lisboa tem um dos pôres do sol mais bonitos do mundo, e visto do Tejo a luz dourada "
                "envolve a cidade — Cristo Rei, 25 de Abril, Belém. É o momento perfeito para celebrar, "
                "para um pedido especial, ou simplesmente para parar e respirar. Esta é a essência da experiência.",
    },
]

ICEBREAKERS = [
    "Quero fazer um passeio ao pôr do sol",
    "É uma experiência privada?",
    "Ideal para casais?",
    "O que está incluído?",
    "Quanto custa?",
    "Ver disponibilidade",
]

WELCOME_MESSAGE = "Olá ⛵️ Sou o Tejo Sailing AI. Pronto para descobrires Lisboa a partir do Rio, ao pôr do sol?"

# Sailboat at sunset stock photo
AVATAR_URL = "https://images.unsplash.com/photo-1530549387789-4c1017266635?w=400&h=400&fit=crop&q=80"

# Sunset over the river theme — warm orange + river blue
THEME = {
    "primary": "#D97543",         # Sunset orange
    "primary_dark": "#A24F26",
    "primary_soft": "#FCEFE6",
    "primary_border": "#F4D2BD",
    "bot": "#2980B9",             # River blue accent
}


async def run():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if not admin:
        print(f"❌ {ADMIN_EMAIL} não encontrado.")
        return
    tid = admin["tenant_id"]
    print(f"Tenant: {tid}")

    src_name = "Tejo Sunset Sailing — Experiências"
    existing_src = await db.data_sources.find_one(
        {"tenant_id": tid, "name": src_name}, {"_id": 0}
    )
    if existing_src:
        source_id = existing_src["id"]
        await db.data_chunks.delete_many({"source_id": source_id})
        print(f"  · Data source existente: {source_id[:8]}…")
    else:
        source_id = str(uuid.uuid4())
        await db.data_sources.insert_one({
            "id": source_id, "tenant_id": tid, "name": src_name,
            "type": "knowledge_base", "url": "",
            "items": len(KNOWLEDGE_CHUNKS), "chunks": len(KNOWLEDGE_CHUNKS),
            "indexed_at": now_iso(), "created_at": now_iso(),
        })
        print(f"  · Data source criada: {source_id[:8]}…")

    for ch in KNOWLEDGE_CHUNKS:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tid, "source_id": source_id,
            "kind": "knowledge", "title": ch["topic"], "text": ch["text"],
            "meta": {"topic": ch["topic"]}, "indexed_at": now_iso(),
        })
    await db.data_sources.update_one(
        {"id": source_id},
        {"$set": {"items": len(KNOWLEDGE_CHUNKS), "chunks": len(KNOWLEDGE_CHUNKS),
                  "indexed_at": now_iso()}},
    )
    print(f"  · {len(KNOWLEDGE_CHUNKS)} chunks indexados")

    existing_agent = await db.agents.find_one(
        {"tenant_id": tid, "name": {"$regex": "Tejo", "$options": "i"}}, {"_id": 0}
    )
    agent_payload = {
        "tenant_id": tid,
        "name": AGENT_NAME,
        "active": True,
        "avatar_url": AVATAR_URL,
        "theme": THEME,
        "role": "Concierge de luxo turístico",
        "goal": "Vender experiências de passeio de veleiro ao pôr do sol no Tejo, personalizar reservas, evocar a experiência emocional e converter em reservas confirmadas pela equipa.",
        "tone": "Emocional, elegante, evocativa, experiencial.",
        "rules": "Português Europeu (ou idioma do utilizador). Foco em experiência premium. Linguagem emocional MAS simples. Nunca inventar preços ou horários. Captar nome+email antes de propor verificação.",
        "system_prompt": SYSTEM_PROMPT,
        "knowledge": "\n\n".join(c["text"] for c in KNOWLEDGE_CHUNKS),
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
        "config": {"max_history": 24, "lead_capture_required": True},
        "updated_at": now_iso(),
    }
    if existing_agent:
        await db.agents.update_one({"id": existing_agent["id"]}, {"$set": agent_payload})
        print(f"  · Agente Tejo Sailing atualizado: {existing_agent['id'][:8]}…")
    else:
        agent_payload["id"] = str(uuid.uuid4())
        agent_payload["created_at"] = now_iso()
        await db.agents.insert_one(agent_payload)
        print(f"  · Agente Tejo Sailing criado: {agent_payload['id'][:8]}…")


if __name__ == "__main__":
    asyncio.run(run())
