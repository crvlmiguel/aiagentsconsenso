"""Seed para o tenant de DEMONSTRAÇÃO (admin@consensoplus.com).
Popula com dados realistas PT-PT de uma imobiliária.
Não toca no tenant principal (demo@consenso.plus)."""
import os
import asyncio
from datetime import datetime, timezone, timedelta
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

from auth import hash_password

load_dotenv(Path(__file__).parent / ".env")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "admin@consensoplus.com"
ADMIN_PASSWORD = "100%Consenso"


def _now(off_min=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=off_min)).isoformat()


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    existing = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if existing:
        print(f"Conta demo {ADMIN_EMAIL} já existe. A saltar.")
        client.close()
        return

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())

    await db.tenants.insert_one({
        "id": tenant_id, "name": "Imobiliária Lisboa",
        "slug": f"imobiliaria-lisboa-{tenant_id[:8]}", "plan": "pro",
        "default_language": "pt", "created_at": _now(),
    })

    await db.users.insert_one({
        "id": user_id, "tenant_id": tenant_id,
        "email": ADMIN_EMAIL, "name": "Maria Silva",
        "role": "owner",
        "password_hash": hash_password(ADMIN_PASSWORD),
        "created_at": _now(),
    })

    await db.agents.insert_one({
        "id": agent_id, "tenant_id": tenant_id,
        "name": "Aria — Assistente Imobiliária",
        "avatar_url": "",
        "welcome_message": "Olá! Sou a Aria. Como posso ajudar com a sua procura de imóvel?",
        "icebreakers": [
            "Quais T2 disponíveis em Lisboa até 400k?",
            "Quero agendar uma visita",
            "Têm imóveis em Cascais?",
        ],
        "tone": "profissional e caloroso",
        "goal": "Qualificar interesse em imóveis, agendar visitas e capturar leads.",
        "system_prompt": "És a Aria, assistente IA da Imobiliária Lisboa. Ajudas clientes a encontrar imóveis em Lisboa e arredores. Responde SEMPRE em Português Europeu (pt-PT), nunca Brasileiro. Sê simpática, objetiva e útil.",
        "rules": "Pede sempre localização desejada, tipologia (T1/T2/T3...) e orçamento. Quando mostrares imóveis, usa os itens recuperados das fontes de dados (preserva título, preço, imagem e link). Se não houver correspondência, cria lead com o interesse e pede contacto. Nunca inventes preços.",
        "api_provider": "emergent", "api_key": "",
        "model_provider": "auto", "model_name": "gpt-5.1",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
            {"key": "send_email", "enabled": False},
            {"key": "webhook", "enabled": False},
        ],
        "knowledge": "A Imobiliária Lisboa opera em Lisboa, Cascais, Sintra, Oeiras e margem sul. Trabalha com compra, venda e arrendamento.",
        "data_source_ids": [source_id], "default_language": "pt",
        "notify_email": ADMIN_EMAIL,
        "channels": {
            "webchat": {"enabled": True},
            "whatsapp": {"enabled": False, "access_token": "", "phone_number_id": "", "verify_token": ""},
            "telegram": {"enabled": False, "bot_token": ""},
        },
        "email": {"enabled": False, "host": "", "port": 587, "secure": "tls",
                  "username": "", "password": "", "from_email": "", "notify_email": ""},
        "active": True, "created_at": _now(),
    })

    # Fonte de dados: catálogo de imóveis
    imoveis = [
        {"title": "T3 Campo de Ourique — Prédio renovado",
         "price": "540 000 €", "location": "Campo de Ourique, Lisboa",
         "description": "T3 com 110m², 2 WC, varanda grande e arrecadação.",
         "image": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=400",
         "link": "https://example.com/imoveis/t3-campo-ourique"},
        {"title": "T2 Chiado — Centro histórico",
         "price": "620 000 €", "location": "Chiado, Lisboa",
         "description": "T2 recuperado no coração do Chiado, 85m², edifício pombalino.",
         "image": "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=400",
         "link": "https://example.com/imoveis/t2-chiado"},
        {"title": "T4 Cascais — Moradia com piscina",
         "price": "1 250 000 €", "location": "Cascais",
         "description": "Moradia T4 com 240m², jardim, piscina aquecida e garagem para 2 carros.",
         "image": "https://images.unsplash.com/photo-1613977257363-707ba9348227?w=400",
         "link": "https://example.com/imoveis/t4-cascais"},
        {"title": "T1 Príncipe Real — Bem localizado",
         "price": "390 000 €", "location": "Príncipe Real, Lisboa",
         "description": "T1 luminoso de 58m², totalmente remodelado, perto de transportes.",
         "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=400",
         "link": "https://example.com/imoveis/t1-principe-real"},
    ]
    await db.data_sources.insert_one({
        "id": source_id, "tenant_id": tenant_id, "agent_id": agent_id,
        "name": "Catálogo Imóveis", "type": "json",
        "status": "ready", "chunks": len(imoveis), "items": len(imoveis),
        "indexed_at": _now(), "created_at": _now(),
    })
    for imv in imoveis:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "source_id": source_id,
            "text": f"{imv['title']} · {imv['location']} · {imv['price']} · {imv['description']}",
            "meta": imv,
            "created_at": _now(),
        })

    # Conversas demo
    demo_convos = [
        {
            "contact_name": "Ana Ferreira", "channel": "webchat", "status": "ai",
            "last_message": "Podia ver um T2 em Campo de Ourique?", "lang": "pt",
            "messages": [
                ("user", "Ana Ferreira", "Olá, procuro um apartamento em Lisboa.", -90),
                ("ai", "Aria", "Olá Ana! Com muito gosto. Que tipologia e zona tem em mente?", -89),
                ("user", "Ana Ferreira", "T2 ou T3 em Campo de Ourique ou Chiado. Até 600k.", -85),
                ("ai", "Aria", "Perfeito. Tenho estas opções que podem encaixar: T3 Campo de Ourique (540 000€) e T2 Chiado (620 000€).", -84),
                ("user", "Ana Ferreira", "Podia ver um T2 em Campo de Ourique?", -2),
            ],
            "intent": {"intent": "imóvel_procura", "category": "vendas", "urgency": "medium", "confidence": 0.91},
            "tags": ["t2", "campo-de-ourique"],
        },
        {
            "contact_name": "João Mendes", "channel": "whatsapp", "status": "closed",
            "last_message": "O agente já me ligou. Obrigado!", "lang": "pt",
            "messages": [
                ("user", "João Mendes", "Boa tarde, tenho interesse em moradias em Cascais.", -240),
                ("ai", "Aria", "Boa tarde! Qual o orçamento máximo?", -239),
                ("user", "João Mendes", "Até 1.5M, com jardim e piscina.", -237),
                ("ai", "Aria", "Tenho esta opção que encaixa: Moradia T4 em Cascais (1 250 000€). Quer que marque uma visita?", -236),
                ("user", "João Mendes", "Sim, gostava. O meu telefone é 912 345 678.", -230),
                ("human", "Maria Silva", "Olá João, vou ligar-lhe em 10 min para agendarmos.", -120),
                ("user", "João Mendes", "O agente já me ligou. Obrigado!", -60),
            ],
            "intent": {"intent": "agendar_visita", "category": "vendas", "urgency": "high", "confidence": 0.94},
            "tags": ["cascais", "moradia", "visita"],
        },
        {
            "contact_name": "Sofia Lopes", "channel": "telegram", "status": "human",
            "last_message": "Está lá? Ainda aguardo resposta.", "lang": "pt",
            "messages": [
                ("user", "Sofia Lopes", "Podem enviar-me mais fotos do T1 Príncipe Real?", -30),
                ("ai", "Aria", "Claro! Pode indicar-me o seu email para enviar galeria completa?", -29),
                ("user", "Sofia Lopes", "sofia.lopes@gmail.com", -28),
                ("human", "Maria Silva", "Olá Sofia, vou enviar agora.", -15),
                ("user", "Sofia Lopes", "Está lá? Ainda aguardo resposta.", -2),
            ],
            "intent": {"intent": "informação_imóvel", "category": "vendas", "urgency": "medium", "confidence": 0.87},
            "tags": ["t1", "principe-real", "fotos"],
        },
    ]

    for c in demo_convos:
        conv_id = str(uuid.uuid4())
        await db.conversations.insert_one({
            "id": conv_id, "tenant_id": tenant_id,
            "channel": c["channel"], "external_user_id": str(uuid.uuid4()),
            "contact_name": c["contact_name"], "contact_avatar": None,
            "status": c["status"],
            "assigned_to": user_id if c["status"] == "human" else None,
            "agent_id": agent_id, "tags": c["tags"], "language": c.get("lang", "pt"),
            "last_message": c["last_message"],
            "last_message_at": _now(c["messages"][-1][3]),
            "unread": 1 if c["status"] == "ai" else (2 if c["status"] == "human" else 0),
            "intent": c["intent"], "structure": None,
            "created_at": _now(c["messages"][0][3]),
        })
        for sender, sname, text, off in c["messages"]:
            await db.messages.insert_one({
                "id": str(uuid.uuid4()), "tenant_id": tenant_id,
                "conversation_id": conv_id,
                "sender": sender, "sender_name": sname, "text": text,
                "cards": [], "meta": {}, "created_at": _now(off),
            })

    # Leads
    for lead in [
        {"name": "Ana Ferreira", "email": "ana.ferreira@example.pt", "phone": "",
         "company": "", "source": "ai", "stage": "qualified", "score": 82,
         "notes": "Procura T2 em Campo de Ourique até 600k."},
        {"name": "João Mendes", "email": "joao.m@example.pt", "phone": "912 345 678",
         "company": "", "source": "ai", "stage": "contacted", "score": 90,
         "notes": "Moradia Cascais, até 1.5M, visita agendada."},
        {"name": "Sofia Lopes", "email": "sofia.lopes@gmail.com", "phone": "",
         "company": "", "source": "ai", "stage": "new", "score": 68,
         "notes": "Pediu fotos do T1 Príncipe Real."},
    ]:
        await db.leads.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            **lead, "conversation_id": None, "tags": [],
            "email_notified": False, "created_at": _now(-30),
        })

    # Ticket
    await db.tickets.insert_one({
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "subject": "Sofia Lopes — aguarda galeria de fotos",
        "description": "Cliente pediu fotos adicionais do T1 Príncipe Real. Enviar galeria completa.",
        "priority": "medium", "status": "open",
        "assigned_to": user_id, "conversation_id": None,
        "tags": ["galeria", "t1"],
        "created_at": _now(-10),
    })

    print(f"✓ Tenant demo criado: {tenant_id}")
    print(f"✓ Login: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    print(f"✓ 3 conversas · 3 leads · 1 ticket · 4 imóveis na fonte")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
