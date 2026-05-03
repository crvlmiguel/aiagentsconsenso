"""Seed demo tenant — Imobiliária Lisboa (PT-PT)."""
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


def _now(off=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=off)).isoformat()


async def seed():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    existing = await db.users.find_one({"email": "demo@consenso.plus"}, {"_id": 0})
    if existing:
        print("Tenant demo já existe. A saltar.")
        return

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    agent_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())

    await db.tenants.insert_one({
        "id": tenant_id, "name": "Imobiliária Lisboa",
        "slug": "imobiliaria-lisboa", "plan": "pro",
        "default_language": "pt", "created_at": _now(),
    })

    await db.users.insert_one({
        "id": user_id, "tenant_id": tenant_id,
        "email": "demo@consenso.plus", "name": "Maria Silva",
        "role": "owner",
        "password_hash": hash_password("demo1234"),
        "created_at": _now(),
    })

    await db.agents.insert_one({
        "id": agent_id, "tenant_id": tenant_id,
        "name": "Aria — Assistente Imobiliária",
        "tone": "profissional e caloroso",
        "goal": "Qualificar interesse em imóveis, agendar visitas e capturar leads.",
        "system_prompt": "És a Aria, assistente IA da Imobiliária Lisboa. Ajudas clientes a encontrar imóveis em Lisboa e arredores. Responde SEMPRE em Português Europeu (pt-PT), nunca Brasileiro. Sê simpática, objetiva e útil.",
        "rules": "Pede sempre localização desejada, tipologia (T1/T2/T3...) e orçamento. Quando mostrares imóveis, usa os itens recuperados das fontes de dados (preserva título, preço, imagem e link). Se não houver correspondência, cria lead com o interesse e pede contacto. Nunca inventes preços.",
        "model_provider": "auto", "model_name": "gpt-5.1",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
            {"key": "send_email", "enabled": False},
            {"key": "webhook", "enabled": False},
        ],
        "knowledge": "Imobiliária Lisboa opera em Lisboa, Cascais, Sintra e Oeiras. Horário: Seg-Sex 9-19h, Sáb 10-14h. Telefone: +351 21 000 0000. Taxa de comissão: 5% + IVA.",
        "data_source_ids": [source_id],
        "default_language": "pt",
        "active": True, "created_at": _now(),
    })

    # Sample data source with seeded chunks & items (pre-indexed demo)
    await db.data_sources.insert_one({
        "id": source_id, "tenant_id": tenant_id,
        "kind": "text", "name": "Catálogo de imóveis (demo)",
        "url": None, "status": "indexed",
        "chunks": 6, "items": 4, "last_indexed_at": _now(), "error": None,
        "created_at": _now(),
    })
    sample_items = [
        {"title": "T3 Campo de Ourique", "price": "€475 000", "image": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=600", "link": "https://example.pt/imoveis/1", "description": "T3 renovado com varanda, 110m², 2 lugares garagem. Zona calma e familiar."},
        {"title": "T2 Chiado", "price": "€385 000", "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600", "link": "https://example.pt/imoveis/2", "description": "T2 no coração do Chiado, 78m², prédio reabilitado. Vista deslumbrante."},
        {"title": "T4 Cascais — vista mar", "price": "€1 250 000", "image": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=600", "link": "https://example.pt/imoveis/3", "description": "Moradia T4 com jardim, piscina e vista mar. 220m², perto da marina."},
        {"title": "T1 Príncipe Real", "price": "€295 000", "image": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600", "link": "https://example.pt/imoveis/4", "description": "T1 moderno, 55m², andar alto. Zona trendy com cafés e galerias."},
    ]
    for it in sample_items:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id, "source_id": source_id,
            "kind": "item", "text": f"{it['title']}\n{it['description']}\nPreço: {it['price']}",
            "meta": it,
        })
    for txt in [
        "A Imobiliária Lisboa tem mais de 50 imóveis em Lisboa, Cascais, Sintra e Oeiras.",
        "Agendamento de visitas: preencher nome, telefone e imóvel de interesse. Visitas Seg-Sáb entre 10h e 18h.",
    ]:
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id, "source_id": source_id,
            "kind": "text", "text": txt, "meta": {"source_title": "Catálogo de imóveis (demo)"},
        })

    # Integrations
    for kind, cat, name, status in [
        ("webchat", "channel", "Web Chat", "connected"),
        ("whatsapp", "channel", "WhatsApp Cloud", "disconnected"),
        ("instagram", "channel", "Instagram DM", "disconnected"),
        ("telegram", "channel", "Telegram Bot", "disconnected"),
        ("messenger", "channel", "Messenger", "disconnected"),
        ("hubspot", "crm", "HubSpot", "disconnected"),
        ("pipedrive", "crm", "Pipedrive", "disconnected"),
        ("salesforce", "crm", "Salesforce", "disconnected"),
        ("webhook", "crm", "Webhook genérico", "disconnected"),
        ("smtp", "email", "SMTP / Email", "disconnected"),
    ]:
        await db.integrations.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "kind": kind, "category": cat, "name": name,
            "status": status, "config": {}, "created_at": _now(),
        })

    # Demo conversations
    convos = [
        {
            "contact_name": "Ana Ferreira", "channel": "webchat", "status": "ai",
            "last": "Procuro T3 em Lisboa até 500k€",
            "msgs": [
                ("user", "Ana Ferreira", "Olá! Estou à procura de casa em Lisboa.", -45),
                ("ai", "Aria", "Olá Ana! Que zona tem em mente e qual a tipologia?", -44),
                ("user", "Ana Ferreira", "Procuro T3 em Lisboa até 500k€", -2),
            ],
            "intent": {"intent": "sales_inquiry", "category": "sales", "urgency": "medium", "confidence": 0.9},
            "tags": ["sales", "t3", "lisboa"],
        },
        {
            "contact_name": "João Mendes", "channel": "whatsapp", "status": "human",
            "last": "O agente já me ligou. Obrigado!",
            "msgs": [
                ("user", "João Mendes", "Quero marcar visita ao T2 em Chiado.", -120),
                ("ai", "Aria", "Com certeza. Qual a sua disponibilidade esta semana?", -118),
                ("user", "João Mendes", "Quinta-feira à tarde.", -115),
                ("human", "Maria Silva", "Olá João, sou a Maria. Agendei para quinta às 16h. Confirma?", -10),
                ("user", "João Mendes", "O agente já me ligou. Obrigado!", -1),
            ],
            "intent": {"intent": "booking", "category": "sales", "urgency": "high", "confidence": 0.95},
            "tags": ["booking", "chiado"],
        },
        {
            "contact_name": "Rita Costa", "channel": "instagram", "status": "closed",
            "last": "Obrigada pela ajuda!",
            "msgs": [
                ("user", "Rita Costa", "Têm imóveis em Cascais?", -2880),
                ("ai", "Aria", "Sim! Temos várias opções em Cascais. Qual o seu orçamento?", -2879),
                ("user", "Rita Costa", "Obrigada pela ajuda!", -2870),
            ],
            "intent": {"intent": "information", "category": "sales", "urgency": "low", "confidence": 0.93},
            "tags": ["cascais"],
        },
    ]

    for c in convos:
        conv_id = str(uuid.uuid4())
        await db.conversations.insert_one({
            "id": conv_id, "tenant_id": tenant_id, "channel": c["channel"],
            "external_user_id": str(uuid.uuid4()), "contact_name": c["contact_name"],
            "contact_avatar": None, "status": c["status"],
            "assigned_to": user_id if c["status"] == "human" else None,
            "agent_id": agent_id, "tags": c["tags"], "language": "pt",
            "last_message": c["last"], "last_message_at": _now(c["msgs"][-1][3]),
            "unread": 1 if c["status"] != "closed" else 0,
            "intent": c["intent"], "structure": None,
            "created_at": _now(c["msgs"][0][3]),
        })
        for sender, sname, text, off in c["msgs"]:
            await db.messages.insert_one({
                "id": str(uuid.uuid4()), "tenant_id": tenant_id,
                "conversation_id": conv_id, "sender": sender,
                "sender_name": sname, "text": text, "cards": [],
                "meta": {}, "created_at": _now(off),
            })

    await db.leads.insert_one({
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "name": "Ana Ferreira", "email": "ana.ferreira@email.pt",
        "phone": "+351 912 345 678", "company": None,
        "source": "ai", "stage": "qualified", "score": 85,
        "tags": ["t3", "lisboa", "até-500k"],
        "notes": "Procura T3 em Lisboa até 500k. Interessada em Campo de Ourique.",
        "conversation_id": None, "crm_synced": False, "created_at": _now(-30),
    })
    await db.tickets.insert_one({
        "id": str(uuid.uuid4()), "tenant_id": tenant_id,
        "subject": "Pedido de segunda visita — T3 Campo de Ourique",
        "description": "Cliente pediu marcação de 2ª visita com o cônjuge.",
        "priority": "medium", "status": "in_progress",
        "assigned_to": user_id, "conversation_id": None,
        "created_at": _now(-60),
    })

    print(f"Seed concluído: tenant {tenant_id} | demo@consenso.plus / demo1234")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
