"""Seed do agente ABBI — Assistente Imobiliário.
Cria um novo agente dedicado no tenant demo (admin@consenso-agents.com)
com 9 imóveis reais extraídos de https://abbimoveis.com/imovel/
"""
import os
import asyncio
from datetime import datetime, timezone
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

ADMIN_EMAIL = "admin@consenso-agents.com"

# 9 imóveis reais extraídos de https://abbimoveis.com/imovel/
PROPERTIES = [
    {
        "ref": "JL-V3",
        "title": "Moradias V3 – Jardim de Lagos",
        "type": "Moradia", "tipologia": "V3",
        "location": "Lagos, Faro",
        "area": "290-434 m²", "bedrooms": 3, "bathrooms": "2-4", "parking": "2-3 lugares",
        "price": "Sob consulta",
        "description": "Moradias V3 modernas em condomínio privado, com piscina, ar condicionado, churrasqueira, cozinha com equipamentos Balay e videoporteiro. A poucos minutos das praias de Lagos.",
        "image": "https://abbimoveis.com/wp-content/uploads/2024/09/31-1200x675.jpg",
        "link": "https://abbimoveis.com/imovel/moradias-v3-lagos/",
        "status": "Disponível",
    },
    {
        "ref": "JL-T2",
        "title": "Apartamentos T2 – Jardim de Lagos",
        "type": "Apartamento", "tipologia": "T2",
        "location": "Lagos, Faro",
        "area": "88,40-128,40 m²", "bedrooms": 2, "bathrooms": 2, "parking": "2 lugares",
        "price": "Sob consulta",
        "description": "Apartamentos T2 em empreendimento moderno, combinando conforto e localização privilegiada junto ao mar.",
        "image": "https://abbimoveis.com/wp-content/uploads/2024/09/30-1200x675.jpg",
        "link": "https://abbimoveis.com/imovel/apartamentos-t2-jardim-de-lagos-copiar/",
        "status": "Disponível",
    },
    {
        "ref": "OXY-T4",
        "title": "Apartamentos T4 – Oxigénio",
        "type": "Apartamento", "tipologia": "T4",
        "location": "Maia, Porto",
        "area": "398,55 m²", "bedrooms": 4, "bathrooms": 5, "parking": "4 lugares",
        "price": "Sob consulta",
        "description": "Empreendimento Oxigénio em construção, alia modernidade, sustentabilidade e conforto. Apartamentos T4 de grandes áreas na Maia.",
        "image": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=1200",
        "link": "https://abbimoveis.com/imovel/apartamentos-t4-oxigenio/",
        "status": "Em construção",
    },
    {
        "ref": "SC-V4",
        "title": "Moradias V4 – S. Caetano",
        "type": "Moradia", "tipologia": "V4",
        "location": "Braga, Braga",
        "area": "326-388,87 m²", "bedrooms": 4, "bathrooms": "2-3", "parking": "3 lugares",
        "price": "Sob consulta",
        "description": "Moradias de São Caetano, área tranquila rodeada de natureza em Braga. Design contemporâneo com áreas generosas.",
        "image": "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=1200",
        "link": "https://abbimoveis.com/imovel/moradias-v4-caetano/",
        "status": "Disponível",
    },
    {
        "ref": "SRV-T1",
        "title": "Apartamentos T1 – Serralves",
        "type": "Apartamento", "tipologia": "T1",
        "location": "Porto, Porto",
        "area": "50 m²", "bedrooms": 1, "bathrooms": 1, "parking": "1-3 lugares",
        "price": "Sob consulta",
        "description": "Edifício Serralves numa das zonas mais nobres do Porto. T1 compacto e elegante numa localização icónica.",
        "image": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=1200",
        "link": "https://abbimoveis.com/imovel/apartamento-t1-serralves/",
        "status": "Em construção",
    },
    {
        "ref": "SRV-T4",
        "title": "Apartamentos T4 – Serralves",
        "type": "Apartamento", "tipologia": "T4",
        "location": "Porto, Porto",
        "area": "172-231,42 m²", "bedrooms": 4, "bathrooms": 4, "parking": "3 lugares",
        "price": "Sob consulta",
        "description": "Edifício Serralves, Porto — T4 de grande área em zona nobre. Acabamentos de elevado padrão.",
        "image": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1200",
        "link": "https://abbimoveis.com/imovel/apartamento-t4-serralves/",
        "status": "Em construção",
    },
    {
        "ref": "QG-T2",
        "title": "Apartamentos T2 – Quinta da Granja",
        "type": "Apartamento", "tipologia": "T2",
        "location": "Granja, Barcelos",
        "area": "100-140 m²", "bedrooms": 2, "bathrooms": 2, "parking": "1-2 lugares",
        "price": "Sob consulta",
        "description": "Apartamentos T2 na Avenida Sidónimo Pais, Granja, Barcelos. Os mais elevados padrões de conforto em localização privilegiada.",
        "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=1200",
        "link": "https://abbimoveis.com/imovel/apartamento-t2-quinta-da-granja/",
        "status": "Disponível",
    },
    {
        "ref": "PC3-T3",
        "title": "Apartamentos T3 – Parque da Cidade III",
        "type": "Apartamento", "tipologia": "T3",
        "location": "Guimarães, Braga",
        "area": "140-220 m²", "bedrooms": 3, "bathrooms": "2-3", "parking": "2 lugares",
        "price": "Sob consulta",
        "description": "Parque da Cidade III em Guimarães — localização privilegiada, permite desfrutar das vistas e proximidade ao parque urbano.",
        "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1200",
        "link": "https://abbimoveis.com/imovel/apartamento-t3-parque-da-cidade/",
        "status": "Em construção",
    },
    {
        "ref": "AN-V3",
        "title": "Moradias V3 – Aldeia Nova",
        "type": "Moradia", "tipologia": "V3",
        "location": "Vila Nova de Famalicão, Braga",
        "area": "160 m²", "bedrooms": 3, "bathrooms": "2-3", "parking": "1-2 lugares",
        "price": "Sob consulta",
        "description": "Moradias Aldeia Nova combinam design contemporâneo com acabamentos de elevada qualidade em Vila Nova de Famalicão.",
        "image": "https://images.unsplash.com/photo-1583608205776-bfd35f0d9f83?w=1200",
        "link": "https://abbimoveis.com/imovel/moradias-v3-aldeia-nova/",
        "status": "Disponível",
    },
]


def _now():
    return datetime.now(timezone.utc).isoformat()


async def seed():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    user = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0})
    if not user:
        print(f"Utilizador {ADMIN_EMAIL} não encontrado. Corre primeiro seed_demo.py.")
        client.close()
        return

    tenant_id = user["tenant_id"]

    # Remove existing ABBI/Abby agent (idempotent)
    existing = await db.agents.find_one({"tenant_id": tenant_id, "$or": [
        {"name": {"$regex": "ABBI"}}, {"name": {"$regex": "Abby"}}
    ]}, {"_id": 0})
    if existing:
        await db.agents.delete_one({"id": existing["id"]})
        await db.data_sources.delete_many({"agent_id": existing["id"]})
        await db.data_chunks.delete_many({"source_id": {"$in":
            [s["id"] for s in await db.data_sources.find({"agent_id": existing["id"]}).to_list(100)]}})
        print("✓ Agente ABBI anterior removido.")

    agent_id = str(uuid.uuid4())
    source_id = str(uuid.uuid4())

    # Create data source
    await db.data_sources.insert_one({
        "id": source_id, "tenant_id": tenant_id, "agent_id": agent_id,
        "name": "Catálogo ABBI Imóveis",
        "type": "website",
        "source_url": "https://abbimoveis.com/imovel/",
        "status": "ready",
        "chunks": len(PROPERTIES),
        "items": len(PROPERTIES),
        "indexed_at": _now(), "created_at": _now(),
    })

    for p in PROPERTIES:
        chunk_text = (
            f"{p['title']} — Referência {p['ref']}. "
            f"Tipo: {p['type']} {p['tipologia']}. "
            f"Localização: {p['location']}. "
            f"Área: {p['area']}. "
            f"{p['bedrooms']} quartos, {p['bathrooms']} WC, {p['parking']}. "
            f"Estado: {p['status']}. "
            f"Preço: {p['price']}. "
            f"{p['description']} "
            f"Link: {p['link']}"
        )
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()), "tenant_id": tenant_id,
            "source_id": source_id,
            "kind": "item",
            "text": chunk_text,
            "meta": {
                "title": p["title"], "price": p["price"], "location": p["location"],
                "image": p["image"], "link": p["link"],
                "description": p["description"],
                "tipologia": p["tipologia"], "type": p["type"],
                "ref": p["ref"], "status": p["status"],
                "area": p["area"], "bedrooms": p["bedrooms"],
            },
            "created_at": _now(),
        })

    # Create ABBI agent
    system_prompt = (
        "És a Abby, assistente imobiliária virtual da ABBI Imóveis (ABB Imóveis). "
        "PERSONALIDADE: profissional, comunicativa e extremamente amigável, sem ser formal ou robótica. "
        "Falas com os clientes como um colega experiente falaria — com calor humano, proximidade e à-vontade. "
        "Ajudas clientes a descobrir imóveis do portfolio ABBI — moradias, apartamentos e empreendimentos "
        "em Lagos, Porto, Braga, Guimarães, Maia, Barcelos, Vila Nova de Famalicão. "
        "IDIOMA: Detectas automaticamente o idioma do cliente e respondes SEMPRE no MESMO idioma. "
        "Se te falarem em Inglês, respondes em Inglês. Alemão em Alemão. Francês em Francês. Espanhol em Espanhol. "
        "Se for Português, usa Português Europeu (pt-PT, NUNCA pt-BR). "
        "Os preços não estão publicados — indica 'Sob consulta' e oferece contacto com a equipa."
    )
    rules = (
        "DINÂMICA DE CONVERSA (VENDEDORA — não recepcionista):\n"
        "1. Mensagens CURTAS e diretas (estilo WhatsApp). Nunca textos longos. Nunca parágrafos.\n"
        "2. Se a resposta for rica, divide em 2 balões: contexto curto + próximo passo concreto.\n"
        "3. SEM perguntas abertas. TERMINA sempre com um call-to-action claro de entre 2 opções (ex.: 'Queres ver fotos ou simular o crédito?').\n"
        "4. Usa emojis com moderação (no máximo 1 por mensagem).\n"
        "\n"
        "APRESENTAÇÃO IMEDIATA DE OPÇÕES (CRÍTICO):\n"
        "• Logo que o cliente mencione ZONA (Lagos, Porto, Braga...) OU TIPOLOGIA (T1/T2/T3/T4/moradia) → apresenta IMEDIATAMENTE 2-3 cards das fontes de dados.\n"
        "• NÃO peças 'mais detalhes' antes de mostrar opções. Mostra primeiro, qualifica depois.\n"
        "• Se tiveres ≥3 opções relevantes, mostra 3. Se tiveres 1-2, mostra essas + sugere cidades próximas.\n"
        "• Nunca inventes imóveis — só usa os que estão nos Dados Recuperados.\n"
        "\n"
        "OBJETIVO DE CONVERSÃO (cada conversa TEM de obter):\n"
        "  • NOME • EMAIL • INTERESSE (zona + tipologia + orçamento ou intenção)\n"
        "Técnica: recolhe os dados NATURALMENTE ao longo da conversa, após mostrar imóveis. Nunca tudo de uma vez.\n"
        "\n"
        "SIMULADOR DE CRÉDITO HABITAÇÃO (USA SEMPRE QUE FIZER SENTIDO):\n"
        "• Se o cliente perguntar 'quanto pago por mês?' ou 'simulação de crédito' → pede VALOR DO IMÓVEL + VALOR DA ENTRADA.\n"
        "• Após mostrar imóveis, PROPÕE proativamente: 'Queres que simule a prestação deste imóvel?'\n"
        "• Fórmula aproximada (PT 2026, Euribor 12m ~2.5% + spread ~1% = taxa anual 3.5%, prazo 30 anos):\n"
        "    empréstimo = preço - entrada\n"
        "    r = 0.035 / 12\n"
        "    n = 30 * 12 = 360\n"
        "    prestação = empréstimo × (r × (1+r)^n) / ((1+r)^n - 1)\n"
        "• Exemplo: imóvel 300.000€, entrada 60.000€ → empréstimo 240.000€ → prestação ~1.078€/mês.\n"
        "• APÓS mostrar o valor, pede IMEDIATAMENTE contacto para consultor financeiro validar: 'Para um consultor te validar estes valores oficialmente, deixa-me o teu email/telefone.'\n"
        "• Indica sempre que é valor INDICATIVO e não vinculativo.\n"
        "\n"
        "QUALIFICAÇÃO DO LEAD:\n"
        "  • HOT: pediu visita OU deixou telefone OU fez simulação + deixou contacto\n"
        "  • WARM: nome + email + interesse claro\n"
        "  • COLD: só fez perguntas gerais\n"
        "\n"
        "Contacto da equipa para fallback: +351 253 142 000 · geral@abborges.pt"
    )

    await db.agents.insert_one({
        "id": agent_id, "tenant_id": tenant_id,
        "name": "Abby — ABBI Imóveis",
        "avatar_url": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=200&h=200&fit=crop",
        "theme": {
            "primary": "#c9a84d",
            "primary_dark": "#a88838",
            "primary_soft": "#FAF4E2",
            "primary_border": "#E8D8A8",
            "bot": "#4e7bfa",
        },
        "welcome_message": "Olá! Como posso ajudar hoje?",
        "icebreakers": [
            "🏠 Comprar e simular prestação",
            "🔑 Procurar casa para arrendar",
            "📈 Imóveis para investimento",
            "📑 Que documentos preciso?",
        ],
        "tone": "profissional, comunicativo, extremamente amigável, conversacional como uma pessoa real",
        "goal": "Apresentar imóveis do catálogo ABBI, qualificar interesse e capturar leads para a equipa comercial.",
        "system_prompt": system_prompt,
        "rules": rules,
        "api_provider": "emergent", "api_key": "",
        "model_provider": "auto", "model_name": "gpt-5.1",
        "tools": [
            {"key": "create_lead", "enabled": True},
            {"key": "create_ticket", "enabled": True},
            {"key": "send_email", "enabled": False},
            {"key": "webhook", "enabled": False},
        ],
        "knowledge": (
            "A ABBI Imóveis (ABB Imóveis) é uma promotora e mediadora imobiliária com "
            "empreendimentos em Lagos (Algarve), Porto, Braga, Guimarães, Maia, Barcelos e "
            "Vila Nova de Famalicão. Catálogo atual: 9 empreendimentos entre moradias V3/V4 e "
            "apartamentos T1/T2/T3/T4. Contacto: +351 253 142 000 · geral@abborges.pt. "
            "Site: https://abbimoveis.com"
        ),
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

    print(f"✓ Agente ABBI criado (id: {agent_id})")
    print(f"✓ Fonte de dados com {len(PROPERTIES)} imóveis indexados")
    print(f"✓ Login para testar: {ADMIN_EMAIL}")
    print("\nURL do widget de teste:")
    backend = os.environ.get("BACKEND_PUBLIC_URL", "<your-domain>")
    print(f"   {backend}/api/widget-test/{tenant_id}/{agent_id}")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
