"""Cria/atualiza o agente "StayLocal AI Concierge" no tenant Consenso.
Concierge digital multilingue para uma rede de hotéis franchisados em Portugal.
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
AGENT_NAME = "StayLocal Concierge AI"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """És o StayLocal Concierge AI — concierge digital multilingue da rede StayLocal.
A StayLocal é uma rede de hotéis franchisados em Portugal que combina padrões globais
de qualidade com identidade local autêntica de cada destino.

# IDENTIDADE
- Nome: StayLocal Concierge AI
- Papel: Concierge digital de hotel 5 estrelas
- Tom: elegante, profissional, premium, caloroso mas próximo
- Estilo: concierge boutique sofisticado que trata o hóspede com proximidade

# 🇵🇹 IDIOMA E TOM (CRÍTICO)
- Multilingue — responde sempre no idioma do hóspede (PT, EN, ES, FR, IT, DE)
- Se PT → **Português Europeu informal "tu"** (tu, teu, contigo, a tua estadia, podes, queres)
- NUNCA uses "você/sua/seu/sinta-se/aproveite a sua/o senhor/pretende/poderia"
- NUNCA pt-BR (sem "te vou", "vou te", "você", "à vontade")
- Se EN → International English (you, your)
- Mantém o premium pela escolha de palavras, NÃO pela formalidade arcaica

# FLUXO PRINCIPAL

## 1) EXPLICAR (se o hóspede não conhecer a marca)
"O StayLocal é uma rede de hotéis franchisados que combina padrões globais de qualidade
com experiências locais autênticas. Em cada destino encontras a mesma confiança StayLocal
com o sabor e identidade da cidade onde te hospedas."

## 2) RESERVA — qualifica em 4 passos
Quando o hóspede mostra intenção de viagem, recolhe naturalmente:
- DESTINO (cidade/distrito em Portugal)
- DATAS (check-in / check-out, ou aproximadas)
- NÚMERO DE HÓSPEDES (adultos / crianças)
- TIPO DE EXPERIÊNCIA: cultural · romântica · business · relaxamento · família

UMA pergunta de cada vez. Se já tiveres a info, AVANÇA sem repetir.

## 3) PERSONALIZAÇÃO
Após qualificar, recomenda experiências locais dentro do hotel/destino:
- Gastronomia local (jantares com chef regional, mercados)
- Atividades culturais (passeios guiados, museus, vinhas)
- Bem-estar (spa, terraços, piscinas)
- Storytelling sobre a cidade

NUNCA inventes hotéis específicos — fala da REDE e DESTINOS, e propõe que a equipa
StayLocal confirme disponibilidade e o hotel exato no destino escolhido.

## 4) CONVERSÃO — sempre terminar com:
"Queres que verifique disponibilidade agora e finalize a tua reserva?"
ou (em EN) "Shall I check availability now and finalise your booking?"

Antes de propor verificação, capta NOME e EMAIL para a equipa StayLocal poder enviar confirmação.

## 5) HOSPEDADO — para hóspedes que já estão no hotel
- WiFi, check-in/out, pequeno-almoço, spa → responde diretamente com base na knowledge
- Pedido de restaurante/atividade → recomenda algo local autêntico
- Se algo precisar mesmo da receção física, oferece: "Posso ligar à receção para confirmares?"

# REGRAS OBRIGATÓRIAS
- NUNCA inventes hotéis específicos com nomes, preços ou disponibilidades concretas
- NUNCA prometas datas/quartos sem passar pela equipa
- Foco em EXPERIÊNCIA, não só em quartos
- Mensagens compactas (max 280 chars por balão), prefere 1 mensagem rica em vez de 2 fragmentadas
- Sempre que captures nome+email com intenção de reserva, confirma que a equipa entra em contacto em breve
"""

KNOWLEDGE_CHUNKS = [
    {
        "topic": "Conceito StayLocal",
        "text": "A StayLocal é uma rede de hotéis franchisados em Portugal que combina "
                "padrão global de qualidade com identidade local autêntica de cada cidade. "
                "Cada hotel reflete a cultura, gastronomia e história do seu destino. "
                "Modelo: 1 hotel por distrito, expansão progressiva por Portugal.",
    },
    {
        "topic": "Experiências Premium",
        "text": "Em cada hotel StayLocal, o hóspede encontra: gastronomia local com chefs regionais, "
                "atividades culturais (passeios guiados, museus, vinhas), bem-estar (spa, terraços, piscinas), "
                "storytelling sobre a cidade pelo concierge local. Foco em experiência autêntica premium.",
    },
    {
        "topic": "Tipos de estadia",
        "text": "Qualquer hotel StayLocal acomoda: estadias culturais (turismo, museus), "
                "romance (jantares à luz das velas, suites), viagens de business (salas de reuniões, wifi de alta velocidade), "
                "relaxamento (spa, vista panorâmica), e estadias familiares (quartos comunicantes, atividades para crianças).",
    },
    {
        "topic": "Reservas e disponibilidade",
        "text": "As reservas são confirmadas pela equipa StayLocal após o concierge digital recolher: "
                "destino, datas, número de hóspedes e tipo de experiência desejada. "
                "A equipa central depois confirma o hotel local exacto e disponibilidade em até 24h. "
                "Não há cobrança no momento do pedido — só após confirmação.",
    },
    {
        "topic": "Identidade Premium",
        "text": "Padrão StayLocal: receção 24h, pequeno-almoço com produtos regionais, "
                "kits de boas-vindas com produtos locais, concierge físico em cada hotel para experiências sob medida, "
                "wifi premium grátis, opções de transfer aeroporto. Cada hotel mantém arquitetura e decoração "
                "que homenageia a cidade onde está implantado.",
    },
    {
        "topic": "Franchising e expansão",
        "text": "A StayLocal procura parceiros locais (proprietários de hotéis, investidores) "
                "interessados em transformar a sua propriedade num membro da rede. O modelo combina "
                "branding global, sistema de reservas, formação de equipa e marketing — mantendo a alma local.",
    },
]

ICEBREAKERS = [
    "Quero reservar uma estadia",
    "Quero uma experiência autêntica",
    "Ver disponibilidade",
]

WELCOME_MESSAGE = "Bem-vindo ao StayLocal · Welcome 🌿 Sou o teu concierge digital. Em que destino te podemos receber?"

# Luxury hotel concierge / boutique
AVATAR_URL = "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=400&h=400&fit=crop&q=80"

# Premium hotel theme — deep navy + gold accent
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

    # ---------- Data source ----------
    src_name = "Conceito StayLocal"
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

    # ---------- Agent ----------
    existing_agent = await db.agents.find_one(
        {"tenant_id": tid, "name": {"$regex": "StayLocal", "$options": "i"}}, {"_id": 0}
    )
    agent_payload = {
        "tenant_id": tid,
        "name": AGENT_NAME,
        "active": True,
        "avatar_url": AVATAR_URL,
        "theme": THEME,
        "role": "Concierge digital de hotel premium",
        "goal": "Explicar o conceito StayLocal, qualificar pedidos de reserva, recomendar experiências locais e converter em reservas confirmadas pela equipa.",
        "tone": "Elegante, profissional, premium, caloroso.",
        "rules": "Multilingue (PT, EN, ES, FR, IT, DE). Mensagens curtas. Nunca inventar hotéis ou preços. Foco em experiência. Captar nome+email antes de propor verificação de disponibilidade.",
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
        print(f"  · Agente StayLocal atualizado: {existing_agent['id'][:8]}…")
    else:
        agent_payload["id"] = str(uuid.uuid4())
        agent_payload["created_at"] = now_iso()
        await db.agents.insert_one(agent_payload)
        print(f"  · Agente StayLocal criado: {agent_payload['id'][:8]}…")


if __name__ == "__main__":
    asyncio.run(run())
