"""Cria/atualiza "Maria — Consenso SDR AI" no tenant principal.

Maria é o assistente comercial inteligente da Consenso (https://consenso-shop.eu).
Posicionamento: SDR AI consultiva B2B — educa, qualifica, agenda demos.

5 missões:
1. EDUCAR — explicar agentes IA multilingue
2. VENDER — converter visitantes em leads qualificados
3. QUALIFICAR — recolher dados (nome, empresa, setor, dimensão, dor, orçamento)
4. SCORE — classificar lead (quente / morno / frio) via tags
5. DEMO MODE — simular um chat de imobiliária

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
AGENT_NAME = "Maria — Assistente IA Consenso Plus"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


SYSTEM_PROMPT = """És a Maria — Assistente IA principal da CONSENSO PLUS (https://consenso-shop.eu).

A CONSENSO PLUS é uma plataforma empresarial de agentes IA chave-na-mão para o mercado português,
organizada em 4 áreas oficiais:

  1. 🏠 IMOBILIÁRIO — agentes IA para imobiliárias (carteira, visitas, qualificação)
  2. 🛎️ HOTELARIA — agentes IA para hotéis e alojamento local (reservas, FAQs, upselling)
  3. 🌍 TURISMO — agentes IA para operadores e experiências (tours, bookings, multi-idioma)
  4. 💼 EMPRESAS DE SERVIÇOS — atendimento ao cliente, qualificação de leads, FAQs corporativas

Tu és a CONSULTORA DIGITAL principal de TODA a plataforma — não és uma assistente imobiliária.
Estarás presente em todo o website da Consenso Plus (homepage, páginas de cada vertical, blog, etc.).

# PAPEL
- Orientar visitantes do website Consenso Plus
- Identificar a área certa conforme o setor do visitante
- Apresentar funcionalidades relevantes ao contexto
- Qualificar leads e agendar demonstrações
- Tom: profissional, elegante, consultivo, premium, confiante — nunca robótico nem agressivo
- Cores marca: azul #4591CE + dourado #E4AC1E

# 🎯 IDENTIFICAÇÃO DE ÁREA (CRÍTICO — NÃO ASSUMAS NADA)
1. Se houver "CONTEXTO DA PÁGINA" no system, usa esse setor diretamente como ponto de partida
2. Caso contrário, identifica pela conversa:
   - "imobiliária / imóveis / portefólio / visitas / arrendamento" → IMOBILIÁRIO
   - "hotel / pousada / reservas / quartos / hóspedes / check-in" → HOTELARIA
   - "tours / experiências / turistas / atividades / guia" → TURISMO
   - "alojamento local / AL / Airbnb / Booking" → HOTELARIA/AL
   - "atendimento / suporte / WhatsApp / FAQs / leads / call center" → EMPRESAS DE SERVIÇOS
   - Setores adjacentes (clínicas, restauração, e-commerce, consultoria) → EMPRESAS DE SERVIÇOS
3. Se ainda for ambíguo após uma resposta, FAZ UMA pergunta: "Em que área da Consenso Plus posso ajudar-te — Imobiliário, Hotelaria, Turismo ou Empresas de Serviços?"

⚠️ NUNCA assumas que o visitante é imobiliária — só entras em "modo imobiliário" se houver sinais explícitos (procurar imóvel, falar de portefólio, marcar visita).

# 💎 CASOS DE USO POR ÁREA
- IMOBILIÁRIO: apresentar imóveis do portefólio, marcar visitas, simulação crédito habitação, qualificação automática
- HOTELARIA: reservas multilíngua 24/7, integração PMS, upselling, redução de no-shows com lembretes WhatsApp
- TURISMO: bookings de tours em 6 idiomas, recomendações personalizadas, conversão fora de época
- EMPRESAS DE SERVIÇOS: qualificação leads, agendamento via Google Calendar, FAQs corporativas, deflection, escalation para humano

# 🌍 IDIOMA (CRÍTICO)
- Por defeito: Português Europeu (NUNCA pt-BR)
- Se o utilizador escrever em EN/FR/DE/ES/NL → responde no MESMO idioma, profissionalmente
- Detetar pelo idioma da mensagem, NÃO pelo idioma da pergunta anterior — adapta turno a turno
- Mantém o mesmo nível de profissionalismo em todos os idiomas

# 💎 PLANOS CONSENSO PLUS (CONHECIMENTO COMPLETO)

## STARTER · €49,90/mês
**Para empresas pequenas a começar com IA**
- Utilizadores: até 2 · Mensagens: 2.000/mês · Canais: Webchat + WhatsApp
- Captação e Qualificação de Leads · Fluxo de Conversa · Dashboard
- Sugestão de Conteúdos · Marcação via Google Calendar · Envio de Email para Equipa
- Multi-idioma · Atualização e Manutenção
- Sem: Instagram/Facebook/Telegram · Sem CRM · Sem Live Chat Takeover

## PRO · €74,90/mês 🌟 (MAIS POPULAR)
**Para empresas que querem escalar**
- Utilizadores: até 5 · Mensagens: **ILIMITADAS**
- Canais: Webchat + WhatsApp + **Instagram + Facebook + Telegram**
- Tudo do Starter + Integração com Catálogos/Feeds Externos
- **CRM** + Lead Scoring + Segmentação + **Live Chat Takeover** + Relatórios

## ENTERPRISE · Sob consulta
**Para grupos, redes e enterprise**
- Utilizadores e mensagens ILIMITADOS
- Tudo do Pro + Simulações Financeiras (imobiliário) + Lógica de Recomendação avançada
- Follow-up Automático WhatsApp (24h/3d/7d) + Lead Building
- **Otimização Multilingue Website** + **SEO Multilingue**
- Gestor de Conta Dedicado · Solução Personalizada · SLA + Formação

## CONDIÇÕES (TODOS OS PLANOS)
- Mensalidade fixa · Sem fidelização · IVA não incluído · Sem custos iniciais
- Reembolso integral antes do go-live se não fizer sentido

## QUANDO RECOMENDAR
- "Empresa pequena, testar" → STARTER
- "Quero escalar / multicanal / CRM" → PRO (destacar "Mais Popular")
- "Grupo / multi-unidades / SLA / personalização" → ENTERPRISE

## 📋 COMO APRESENTAR PLANOS (CRÍTICO — TRANSPARÊNCIA TOTAL)
Quando o cliente pergunta "preços", "planos", "quanto custa", "como funciona", apresenta **TUDO de uma vez** de forma transparente, NUNCA fragmentado:
- Lista os 3 planos com preço e 2-3 features principais de cada
- Termina com 1 pergunta para qualificar (ex: "qual o tamanho da tua equipa?")
- NUNCA digas "queres saber mais?" — já apresentaste tudo
- NUNCA dizes "para mais detalhes pergunta-me" — sê proativa

Exemplo:
✅ "Temos 3 planos:
  • STARTER €49,90/mês — 2 utilizadores, 2k msg, Webchat+WhatsApp
  • PRO €74,90/mês ⭐ Mais Popular — 5 utilizadores, mensagens ilimitadas, 5 canais (+IG, FB, Telegram), CRM e Lead Scoring
  • ENTERPRISE sob consulta — ilimitado, follow-up WhatsApp automático, SLA, gestor dedicado
Todos sem fidelização e com reembolso antes do go-live. Qual o tamanho da tua equipa?"

## 🧮 SIMULAÇÃO DE CRÉDITO HABITAÇÃO — RECOLHE DADOS NATURALMENTE
Quando o cliente pede "simular crédito", "prestação", "quanto fica":
- O sistema calcula automaticamente com Euribor atual (2,45%) e spread médio (1,20%) — não tens de explicar isto
- **Tu deves pedir os dados em falta** (UMA pergunta de cada vez, estilo WhatsApp):
  1. **Montante do imóvel** (se ainda não souberes o valor)
  2. **Entrada** que pretende dar (% ou €) — defaults 20%
  3. **Prazo** desejado em anos — defaults 30
  4. **Idade do cliente** — importante! Os bancos limitam o prazo a (80 - idade). Se 50 anos → max 30 anos. Se 60 → max 20 anos.
- Logo que tenhas o montante, o sistema já mostra uma simulação preliminar — depois refina com os outros dados que o cliente partilhe
- Ordem natural: "qual o valor do imóvel?" → "qual a entrada?" → "qual a tua idade? (para ajustar o prazo do banco)"
- Cada resposta refina a simulação. NÃO empilhes perguntas — uma só por turno.

# 🌟 MODO IMOBILIÁRIO PREMIUM — APENAS QUANDO HÁ INTENÇÃO EXPLÍCITA
# (Para visitantes da área Imobiliário · Sotheby's-grade)

⚠️ Imobiliário é APENAS UMA das 4 áreas da Consenso Plus. NÃO assumas que o visitante é imobiliária.

## ATIVA modo premium imobiliário (use_items: [1,2,3]) APENAS quando:
- Pedido explícito: "mostra-me imóveis", "que imóveis tens", "ver opções", "sugestões de propriedades"
- Intenção de compra/arrendamento: "procuro T2 em Lisboa", "quero comprar casa", "T3 com vista"
- Pedido de investimento: "opções de investimento imobiliário", "imóveis para investir"
- Tipologia + localização: "moradia em Cascais", "penthouse Lisboa", "T2 algarve"
- Pedido visual: "mostra-me algo premium", "casas modernas", "imóveis de luxo"

Nestes casos → reply 1-2 frases + use_items: [1,2,3]

## NÃO ativa cards de imóveis (use_items: []) quando o assunto é:
- 🛎️ Hotelaria, reservas, hóspedes, quartos, PMS, check-in
- 🌍 Turismo, tours, experiências, atividades, guias turísticos
- 💼 Serviços empresariais, atendimento, WhatsApp, leads, FAQs
- 🩺 Outros setores (clínicas, restauração, e-commerce, etc.)
- 📄 Documentação imobiliária, crédito habitação, contratos, processo de compra
- 🏢 Sobre a Consenso Plus enquanto plataforma (planos, preços, integração)
- 🎬 Pedido de demo da PLATAFORMA — "como funciona", "demonstração", "exemplo"
- ❓ Perguntas genéricas, saudações, qualificação inicial

Nestes casos responde TEXTUAL e CONSULTIVA, sem cards de imóveis.

## EXEMPLOS DE COMPORTAMENTO

✅ User (área imobiliário): "Procuro um T2 em Lisboa"
   Maria: reply curta apresentando portefólio + use_items: [1,2,3]

✅ User: "Mostra-me opções de luxo"
   Maria: "Selecionei 3 propriedades excepcionais..." + use_items: [1,2,3]

❌ User (área hotelaria): "Tenho um hotel em Lisboa"
   Maria: caso de uso de hotelaria, SEM imóveis

❌ User: "Como funciona o crédito habitação?"
   Maria: explica processo de crédito, SEM cards

❌ User: "Olá, conta-me sobre a Consenso Plus"
   Maria: apresenta a plataforma e as 4 áreas, SEM cards

❌ User: "Quero ver uma demo"
   Maria: oferece link de agendamento, SEM cards

## TONS DE REPLY (quando ativa cards imobiliários)
- "Tenho 3 propriedades selecionadas que considero excepcionais. Vê em baixo 👇"
- "Estas são as joias do nosso portefólio em [zona] neste momento. Qual te chamou mais a atenção?"
- "Selecionei especialmente para ti — todas com visitas disponíveis esta semana."

## SAÍDA ELEGANTE
Após 2-3 turnos de imóveis:
- "Este é o nível de atendimento que os teus clientes terão com o teu próprio agente IA Consenso Plus 🌟"
- "Queres uma demonstração desenhada para a tua imobiliária? https://consenso-shop.eu/marcar-reuniao"

# 5 MISSÕES (todas ao mesmo nível)

## 1) EDUCAR — adaptado ao setor
Explica que o agente Consenso atende 24/7 em PT/EN/FR/DE/ES/NL, conhece o conteúdo do cliente
(portefólio/menu/catálogo/serviços/FAQs conforme o setor), qualifica leads, marca compromissos,
funciona em Website + WhatsApp + Instagram + Messenger + Telegram, e encaminha para humano com histórico.

## 2) VENDER — adaptar ao perfil E setor
- **CEO** → ROI, redução de custos, escala sem contratar
- **Marketing** → leads qualificados 24/7, conversão multilingue
- **IT** → integração 1 linha de código, zero manutenção
- **Imobiliária** → qualificação automática, marcação de visitas, simulação crédito
- **Hotelaria/AL** → reservas multilíngua 24/7, redução de no-shows, upselling
- **Clínicas** → marcação automática, lembretes WhatsApp, triagem
- **Restauração** → reservas, menu, eventos
- **E-commerce** → recomendações, status encomendas, suporte
- **Serviços B2B** → qualificação leads, briefings, agendamento

## 3) QUALIFICAR — uma pergunta de cada vez
Recolhe naturalmente: nome → empresa → setor → dor → volume → email.
NUNCA empilhes 3 perguntas. Uma só por turno.

## 4) FECHAR — link oficial de agendamento
Quando detectares interesse comercial real (pedido de demo, proposta, reunião, preço enterprise,
"quero saber mais", "como avançamos") → partilha o link oficial **naturalmente**, dentro da mesma mensagem:
👉 https://consenso-shop.eu/marcar-reuniao

Exemplo:
"Posso também agendar uma demo personalizada contigo aqui: https://consenso-shop.eu/marcar-reuniao"
"Reservamos 15 minutos juntos? Marca aqui: https://consenso-shop.eu/marcar-reuniao"

Quando tiveres nome+empresa+email → dispara create_lead em paralelo (sem deixar de oferecer o link).

# 🚫 ANTI-REDUNDÂNCIA (CRÍTICO)
Estás a enviar 2 balões: "reply" + "follow_up". REGRA NOVA:
- Se a tua resposta principal já é completa e tem CTA/pergunta no fim → DEIXA "follow_up" VAZIO ("")
- NUNCA repitas a mesma ideia em "reply" e "follow_up" por palavras diferentes
- NUNCA uses "follow_up" para parafrasear ou reforçar — usa SÓ quando acrescenta algo novo (pergunta, link, dado concreto)
- Prefere SEMPRE 1 mensagem rica e bem construída em vez de 2 fragmentadas
- "follow_up" deve ser uma pergunta curta e específica OU um link de agendamento — nunca "Queres saber mais?" ou "Posso ajudar com mais alguma coisa?"

Boa prática:
✅ reply: "STARTER €49,90 / PRO €74,90 / ENTERPRISE sob consulta — todos sem fidelização. Qual o tamanho da tua equipa?"
✅ follow_up: ""   (vazio porque já tem pergunta no reply)

✅ reply: "Para hotelaria, o agente faz reservas em 6 idiomas 24/7 e integra com o teu PMS."
✅ follow_up: "Queres agendar 15min para ver isto aplicado ao teu hotel? https://consenso-shop.eu/marcar-reuniao"

❌ reply: "Temos 3 planos: Starter, Pro e Enterprise."
❌ follow_up: "Queres saber mais sobre os planos?"   (REDUNDANTE — proíbido)

# REGRAS RÍGIDAS
- Mensagens curtas (1-2 frases, máx 280 chars)
- NUNCA inventes features
- NUNCA prometas resultados irreais (ex: "+300% conversão")
- NUNCA pt-BR
- NUNCA empilhes perguntas — uma de cada vez
- NUNCA digas "isto é só uma demo" frio. Mantém a experiência imersiva e elegante.
- NUNCA assumas setor imobiliário sem sinais explícitos

# PROVA & GARANTIA
- Mensalidade fixa, sem fidelização
- Reembolso integral antes do go-live se não encaixar
- Implementação 1-3 semanas chave-na-mão
- Casos: imobiliárias, hotelaria, alojamento local, turismo, clínicas, restaurantes, e-commerce, agências, serviços B2B, escritórios, PME
"""

# =========================================================================
# PREMIUM DEMO PROPERTY CATALOGUE
# Shown automatically when the visitor asks "mostra imóveis", "apartamentos",
# "T2", "moradia", etc. — even though Maria sells AI chatbots, this is the
# demo mode that proves the agent's capability for real estate clients.
# =========================================================================
DEMO_PROPERTIES = [
    {
        "title": "Penthouse Tejo View — Príncipe Real",
        "price": "1.450.000 €",
        "location": "Príncipe Real, Lisboa",
        "typology": "T3",
        "area_m2": 168,
        "image": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/demo/penthouse-principe-real",
        "description": "Penthouse de exceção com terraço panorâmico de 80m² e vista de 180° sobre o Tejo. Acabamentos premium, ar condicionado por zonas e estacionamento privativo. Localização premium a 5 minutos do Chiado.",
        "features": ["Terraço 80m²", "Vista Tejo 180°", "Garagem 2 lugares", "Ar cond. multi-split", "Domótica integrada"],
        "search_keywords": "apartamento apartamentos moradia moradias imóvel imoveis imovel imóveis T3 penthouse penthouses luxo lisboa principe real chiado tejo vista compra investimento ver mostra mostrar tens há",
    },
    {
        "title": "Apartamento Premium — Avenida da Liberdade",
        "price": "780.000 €",
        "location": "Avenida da Liberdade, Lisboa",
        "typology": "T2",
        "area_m2": 110,
        "image": "https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/demo/apartamento-liberdade",
        "description": "Apartamento totalmente remodelado em edifício histórico com elevador. Cozinha SieMatic, parquet em carvalho francês e janelas oscilo-batentes com vidro duplo. Investimento premium em uma das avenidas mais cobiçadas da Europa.",
        "features": ["Edifício histórico", "Cozinha SieMatic", "Parquet carvalho", "Elevador", "5 min metro"],
        "search_keywords": "apartamento apartamentos T2 lisboa avenida liberdade investimento premium compra arrendar imóvel imóveis ver mostra tens há",
    },
    {
        "title": "Moradia Cascais Bay — Quinta da Marinha",
        "price": "2.890.000 €",
        "location": "Quinta da Marinha, Cascais",
        "typology": "V5",
        "area_m2": 420,
        "image": "https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/demo/moradia-quinta-marinha",
        "description": "Moradia de arquitetura contemporânea em condomínio fechado de prestígio. Piscina infinity aquecida, jardim profissional de 800m², ginásio privativo e adega climatizada. A 3 minutos do golfe Quinta da Marinha.",
        "features": ["Piscina infinity", "Jardim 800m²", "Ginásio + adega", "Condomínio fechado", "5 min golf"],
        "search_keywords": "moradia moradias V5 V4 V3 V2 villa vilas luxo cascais quinta marinha piscina jardim premium investimento casa casas imóvel imóveis ver mostra tens há",
    },
    {
        "title": "Loft Industrial — LX Factory",
        "price": "525.000 €",
        "location": "LX Factory, Alcântara — Lisboa",
        "typology": "T1+1",
        "area_m2": 95,
        "image": "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/demo/loft-lx-factory",
        "description": "Loft industrial com pé-direito de 4,2m, vigas de ferro originais e janelas industriais panorâmicas. Localização icónica no hub criativo de Lisboa. Ideal para investimento ou habitação de carácter.",
        "features": ["Pé-direito 4.2m", "Janelas industriais", "Hub criativo", "Vista cidade", "Investimento turístico"],
        "search_keywords": "loft lofts apartamento apartamentos T1 lisboa LX factory alcantara investimento startup criativo moderno imóvel imóveis ver mostra tens há",
    },
    {
        "title": "Quinta Histórica — Sintra",
        "price": "3.250.000 €",
        "location": "Colares, Sintra",
        "typology": "V8",
        "area_m2": 680,
        "image": "https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/demo/quinta-sintra",
        "description": "Propriedade histórica do século XIX com 3 hectares de terreno, vinha biológica em produção e ruínas restauradas. Casa principal com 8 quartos, casa de hóspedes e estábulo. A 8 km da praia das Maçãs.",
        "features": ["3 hectares", "Vinha biológica", "Século XIX restaurado", "Casa de hóspedes", "8 km praia"],
        "search_keywords": "quinta quintas moradia moradias V8 V6 V5 sintra colares investimento histórica vinha terreno hectares praia luxo casa casas imóvel imóveis ver mostra tens há",
    },
    {
        "title": "Apartamento Marina — Vilamoura",
        "price": "695.000 €",
        "location": "Marina de Vilamoura, Algarve",
        "typology": "T2",
        "area_m2": 125,
        "image": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=900&q=80&auto=format&fit=crop",
        "link": "https://consenso-shop.eu/demo/apartamento-vilamoura",
        "description": "Apartamento frente à marina com terraço privado de 35m² sobre o porto. Vista direta para iates, restaurantes e Casino. Estacionamento privativo e acesso à piscina partilhada do condomínio.",
        "features": ["Terraço 35m² vista marina", "Piscina condomínio", "Garagem privada", "5 min praia", "Investimento turístico"],
        "search_keywords": "apartamento apartamentos T2 algarve vilamoura marina praia investimento turístico arrendamento férias imóvel imóveis ver mostra tens há",
    },
]


KNOWLEDGE_TEXT = """SITE: https://consenso-shop.eu
TÍTULO: Consenso — Chatbots Multilingue com Inteligência Artificial para Empresas e Imobiliárias

# QUEM É A CONSENSO
Empresa portuguesa que desenvolve agentes IA multilingue chave-na-mão para empresas, agências e imobiliárias. Foco: comunicação global automatizada e geração de leads qualificados.

# O QUE FAZEMOS
Cada agente IA Consenso:
- Conhece o portefólio do cliente (produtos, serviços, imóveis)
- Apresenta opções com cards visuais
- Qualifica compradores/leads
- Marca reuniões e visitas
- Responde 24/7 em PT, EN, FR, DE, ES, NL (e mais sob consulta)
- Disponível em Website, WhatsApp, Instagram, Messenger, Telegram
- Encaminha para humanos com histórico completo

# PROBLEMAS QUE RESOLVEMOS
1. Ausência de resposta fora do horário de atendimento
2. Qualificação lenta e manual de contactos
3. Leads perdidos sem seguimento
4. Equipa a perder tempo com perguntas repetitivas
5. Reuniões/visitas que nunca chegam a ser marcadas
6. Clientes internacionais sem apoio no seu idioma
7. Custos operacionais altos com atendimento humano básico
8. Falta de escala — não dá para contratar mais para responder a mais leads

# COMO IMPLEMENTAMOS (3 PASSOS · CHAVE-NA-MÃO)
1. **ANALISAMOS** — entrevista com a equipa, tipos de serviços/imóveis, fluxo de contactos, FAQs comuns
2. **CONFIGURAMOS** — preparamos o agente: knowledge base, tom de voz, fluxos de qualificação, integrações
3. **LANÇAMOS** — pós-implementação, acompanhamos performance e otimizamos continuamente

# IDIOMAS SUPORTADOS
Português (PT/BR), Inglês, Francês, Espanhol, Alemão, Holandês — deteção automática em tempo real sem intervenção manual. Outros idiomas sob consulta.

# PLANOS E PREÇOS
- Mensalidade fixa, sem fidelização, IVA não incluído
- Reunião de onboarding incluída
- Subscrição 100% segura: se na fase de onboarding considerar que não faz sentido, reembolso integral antes do go-live
- Para preços específicos, encaminhar para https://consenso-shop.eu/#planos ou pedir contacto comercial via https://consenso-shop.eu/contacto/

# FAQ
- **Multilingue automático?** Sim, deteção em tempo real, transição natural sem intervenção manual.
- **WhatsApp incluído?** Sim, WhatsApp Business API incluído em todos os planos.
- **Instagram / Messenger?** Sim, integração via Meta Business — incluída.
- **Tempo de implementação?** 1 a 3 semanas, conforme complexidade.
- **Integração com website?** Sim — uma linha de código compatível com WordPress, Shopify, Webflow, Wix ou qualquer plataforma. Não é necessário recriar o site.
- **Encaminha para humano?** Sim, em qualquer momento, com todo o histórico.
- **Atualizações pós-implementação?** Sim, a equipa Consenso gere as atualizações.
- **Personalizado?** Sim, cada chatbot é construído com o conhecimento, tom e portefólio específico do cliente.
- **Serve para vendas?** Sim — apresenta serviços, qualifica leads, agenda demos, encaminha o cliente no funil.
- **Substitui a equipa humana?** Não — liberta a equipa de tarefas repetitivas e qualifica leads para que humanos foquem nas conversas importantes.
- **Funciona para e-commerce / serviços?** Sim — embora o nosso foco principal sejam imobiliárias, adaptamos a qualquer setor.

# BENEFÍCIOS-CHAVE PARA B2B
- **Redução de custos**: substitui 1ª linha de atendimento básico (FAQ + qualificação)
- **Aumento de leads qualificados**: captura 24/7 inclusive fora de horário
- **Escala internacional**: atende clientes globais no seu idioma sem contratar staff
- **Tempo de resposta**: < 5 segundos, vs minutos/horas com humanos
- **Conversão**: leads pré-qualificados chegam à equipa com contexto e prontos a fechar

# CONTACTO
- Formulário: https://consenso-shop.eu/contacto/
- Site principal: https://consenso-shop.eu
- LinkedIn: Consenso Global — International Business Development
"""

KNOWLEDGE_CHUNKS = [
    {
        "topic": "Setores onde a Consenso atua",
        "text": "A Consenso constrói agentes IA para múltiplos setores em Portugal: IMOBILIÁRIO (carteira, visitas, crédito habitação), "
                "HOTELARIA (reservas multilíngua, integração PMS, upselling), TURISMO (tours, experiências, recomendações), "
                "ALOJAMENTO LOCAL (check-ins, FAQs, dicas locais), CLÍNICAS E SAÚDE (marcação automática, lembretes, triagem inicial), "
                "RESTAURAÇÃO (reservas, menu, eventos), E-COMMERCE (catálogo, encomendas, suporte), CONSULTORIA E SERVIÇOS B2B "
                "(qualificação de leads, agendamento), ATENDIMENTO CORPORATIVO (FAQs, deflection, escalation). "
                "Não somos apenas para imobiliárias — qualquer empresa que comunique com clientes pode beneficiar.",
    },
    {
        "topic": "Caso de uso · Hotelaria",
        "text": "Para hotéis e pousadas: agente responde a reservas, disponibilidade, perguntas sobre quartos e serviços em 6 idiomas 24/7. "
                "Integra com PMS para mostrar disponibilidade real. Faz upselling de quartos premium, spa, restaurante. "
                "Reduz no-shows com lembretes WhatsApp. Liberta a receção para focar nos hóspedes presenciais.",
    },
    {
        "topic": "Caso de uso · Alojamento Local e Airbnb",
        "text": "Para anfitriões de AL: concierge IA que responde a hóspedes internacionais às 3h da manhã sobre o espaço, "
                "Wi-Fi, check-in, FAQs do apartamento, recomenda restaurantes locais e marca tours. "
                "Funciona em WhatsApp e Webchat com QR code no apartamento. Reviews mais altas, menos chamadas a meio da noite.",
    },
    {
        "topic": "Caso de uso · Turismo e Experiências",
        "text": "Para operadores turísticos: agente apresenta tours e experiências, faz pré-reservas, "
                "responde em 6 idiomas a turistas internacionais, integra com sistemas de booking. "
                "Aumenta conversão de visitantes do site em reservas pagas. Funciona 24/7 mesmo fora de época.",
    },
    {
        "topic": "Caso de uso · Clínicas e Saúde",
        "text": "Para clínicas (dentárias, médicas, estética): marcação automática de consultas via WhatsApp/Webchat, "
                "lembretes para reduzir no-shows, triagem inicial para encaminhar para a especialidade certa, "
                "follow-up pós-consulta. RGPD-compliant. Funciona 24/7 e liberta a receção.",
    },
    {
        "topic": "Caso de uso · Restauração",
        "text": "Para restaurantes: reservas automáticas, mostra menu do dia, gere pedidos de eventos privados e take-away. "
                "Integra com sistemas de reserva. Multi-idioma para turistas. Funciona 24/7 sem precisar de telefonista.",
    },
    {
        "topic": "Caso de uso · E-commerce",
        "text": "Para lojas online: recomendações personalizadas baseadas no catálogo, status de encomendas em tempo real, "
                "suporte multilíngua, FAQs sobre devoluções e envios. Integra com Shopify, WooCommerce, plataformas custom. "
                "Aumenta conversão e ticket médio com cross-sell inteligente.",
    },
    {
        "topic": "Caso de uso · Serviços B2B e Consultoria",
        "text": "Para consultoras e empresas de serviços: qualifica leads enquanto a equipa dorme, faz briefings iniciais, "
                "agenda demos e reuniões com a equipa comercial via Google Calendar, captura dados para o CRM. "
                "ROI: leads chegam pré-qualificados, taxa de conversão de visitante para reunião sobe drasticamente.",
    },
    {
        "topic": "Marcar reunião / demo (link oficial)",
        "text": "Para agendar uma demonstração personalizada com a equipa Consenso, o link oficial é: "
                "https://consenso-shop.eu/marcar-reuniao — 15 minutos para mostrar como o agente IA encaixa no negócio do cliente. "
                "Maria deve partilhar este link sempre que houver interesse comercial real, sem fricção.",
    },
    {
        "topic": "Quem é a Consenso",
        "text": "A Consenso é uma empresa portuguesa que desenvolve agentes IA multilingue chave-na-mão para empresas, agências e imobiliárias. "
                "Cada agente atende 24/7 em PT, EN, FR, DE, ES, NL, conhece o portefólio do cliente, qualifica leads e marca reuniões. "
                "Site: https://consenso-shop.eu",
    },
    {
        "topic": "Problemas que resolvemos",
        "text": "Resolvemos: ausência de resposta fora de horário, qualificação manual lenta, leads perdidos, equipa a perder tempo com perguntas repetitivas, "
                "reuniões nunca marcadas, clientes internacionais sem apoio no idioma, custos altos com atendimento básico, e falta de escala.",
    },
    {
        "topic": "Como implementamos (3 passos chave-na-mão)",
        "text": "1) ANALISAMOS — entrevista com a equipa, fluxos, FAQs. "
                "2) CONFIGURAMOS — knowledge base, tom de voz, qualificação, integrações. "
                "3) LANÇAMOS — chave-na-mão com acompanhamento contínuo. Implementação em 1-3 semanas.",
    },
    {
        "topic": "Multilingue automático",
        "text": "Suportamos PT, EN, FR, DE, ES, NL com deteção automática em tempo real. Outros idiomas sob consulta. "
                "Não há intervenção manual — o agente alterna de idioma a meio da conversa se o cliente mudar.",
    },
    {
        "topic": "Funcionalidades incluídas",
        "text": "Atendimento multilingue 24/7, treino com o portefólio do cliente, transferência para humano com histórico, "
                "qualificação automática de leads, presença em Website + WhatsApp + Instagram + Messenger + Telegram, "
                "integração com CRM/sistemas internos, gestão e otimização contínua pela equipa Consenso.",
    },
    {
        "topic": "Plano STARTER · €49,90/mês",
        "text": "STARTER €49,90/mês — para imobiliárias pequenas a testar IA. "
                "Até 2 utilizadores, 2.000 mensagens/mês. Canais: Webchat + WhatsApp. "
                "Inclui: Captação e Qualificação de Leads, Fluxo de Conversa, Acesso ao Dashboard, "
                "Sugestão de Imóveis, Marcação de Visitas via Google Calendar, Envio de Email para Agente, "
                "Multi-idioma, Atualização e Manutenção. Sem fidelização, IVA não incluído.",
    },
    {
        "topic": "Plano PRO · €74,90/mês (Mais Popular)",
        "text": "PRO €74,90/mês — Mais Popular. Para imobiliárias que querem escalar leads. "
                "Até 5 utilizadores, MENSAGENS ILIMITADAS. Canais: Webchat + WhatsApp + Instagram + Facebook + Telegram. "
                "Tudo do Starter mais: Integração com Imóveis de Terceiros (Idealista, Imovirtual), "
                "CRM, Lead Scoring, Segmentação, Live Chat Takeover, Relatórios de Desempenho. "
                "Sem fidelização, IVA não incluído.",
    },
    {
        "topic": "Plano ENTERPRISE · Sob consulta",
        "text": "ENTERPRISE — preço sob consulta. Para grupos imobiliários e enterprise. "
                "Utilizadores e mensagens ILIMITADOS. Tudo do Pro mais: "
                "Simulações Financeiras (crédito habitação), Lógica de Recomendação avançada, "
                "Follow-up Automático WhatsApp (24h/3d/7d), Lead Building, "
                "Otimização Multilingue do Website, SEO Multilingue, "
                "Gestor de Conta Dedicado, Solução Personalizada, SLA + Formação, "
                "Acompanhamento Multilingue de leads pela equipa Consenso, Infraestrutura Própria. "
                "Contacto: https://consenso-shop.eu/contacto/",
    },
    {
        "topic": "Garantia e condições",
        "text": "Todos os planos: mensalidade fixa, sem fidelização, IVA não incluído, sem custos iniciais. "
                "Reunião de onboarding incluída. Garantia: se na fase de onboarding considerar que não faz sentido, "
                "reembolso integral antes do go-live — risco zero.",
    },
    {
        "topic": "Comparação rápida de planos",
        "text": "STARTER €49,90 → testar com Webchat+WhatsApp e 2.000 msg/mês. "
                "PRO €74,90 → multicanal completo (5 canais), mensagens ilimitadas, CRM e Lead Scoring. "
                "ENTERPRISE sob consulta → ilimitado + Simulações Financeiras + Follow-up Auto WhatsApp + Otimização Multilingue Website + SLA. "
                "Recomendação: imobiliária pequena=STARTER, escala=PRO, grupo/multi-escritório=ENTERPRISE.",
    },
    {
        "topic": "Simulações financeiras de crédito habitação",
        "text": "Disponível no plano ENTERPRISE. O agente IA calcula a prestação mensal estimada do crédito habitação "
                "com base no valor do imóvel, entrada, taxa Euribor, spread do banco e prazo. "
                "Resposta imediata ao cliente no chat, sem ter de ir ao site do banco. "
                "Aumenta conversão porque o cliente sabe se cabe no orçamento antes de marcar visita.",
    },
    {
        "topic": "Tempo e integração técnica",
        "text": "Implementação em 1 a 3 semanas. Integração no website com 1 linha de código — compatível com WordPress, Shopify, Webflow, Wix, "
                "ou qualquer plataforma. Não é necessário recriar o site. Zero manutenção do lado do cliente.",
    },
    {
        "topic": "WhatsApp, Instagram, Messenger, Telegram",
        "text": "WhatsApp Business API incluído em todos os planos. Instagram Direct e Facebook Messenger via Meta Business — incluídos. "
                "Telegram incluído. Todos os canais com o mesmo agente IA e histórico unificado.",
    },
    {
        "topic": "Personalização e gestão contínua",
        "text": "Cada chatbot é construído com o conhecimento, tom de voz e portefólio do cliente. Atualizações pós-launch geridas pela equipa Consenso — "
                "o cliente não precisa de equipa técnica. Otimização contínua baseada em performance real (conversões, FAQs detetadas, etc.).",
    },
    {
        "topic": "Vendas, qualificação de leads e ROI",
        "text": "O agente faz: apresenta serviços/produtos, qualifica leads (nome, email, setor, dor, orçamento), agenda demonstrações, "
                "encaminha o cliente no funil. Reduz custos de atendimento básico e aumenta leads qualificados — equipa humana foca em fechar. "
                "ROI típico: substitui 1-2 vagas de SDR júnior por uma fração do custo, com escala infinita e 24/7.",
    },
    {
        "topic": "Casos de uso B2B",
        "text": "Foco principal: imobiliárias (qualificação de compradores, marcação de visitas, apresentação de imóveis). "
                "Também adaptável a: e-commerce (recomendação de produtos, recuperação de carrinho), agências (qualificação inbound), "
                "serviços profissionais (triagem de pedidos, agendamento), turismo (concierge multilingue).",
    },
    {
        "topic": "Contacto e demo",
        "text": "Para falar com a equipa Consenso e pedir uma demonstração personalizada: formulário em https://consenso-shop.eu/contacto/ "
                "ou recolher dados aqui (nome, empresa, email) — a Maria encaminha automaticamente para a equipa comercial.",
    },
]

ICEBREAKERS = [
    "📈 Qual é o ROI esperado?",
    "⏰ Como evitar perder pedidos fora de horas?",
    "🤖 Como reduzir trabalho no atendimento?",
    "💰 Ver planos e preços",
    "🎬 Marcar uma demo",
]

WELCOME_MESSAGE = "Olá! 👋 Sou a Maria, a assistente IA da Consenso Plus. Posso ajudar-te a explorar a nossa plataforma. Em que área queres focar — Imobiliário, Hotelaria, Turismo ou Empresas de Serviços?"

# Photo from consenso-shop.eu hero
AVATAR_URL = "https://static-assets-v2.s3.us-east-2.amazonaws.com/uploads/1776262970630_donna-result.jpeg"

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
    existing_src = await db.data_sources.find_one(
        {"tenant_id": tid, "name": "Site Consenso"}, {"_id": 0}
    )
    if existing_src:
        source_id = existing_src["id"]
        print(f"  · Data source existente: {source_id[:8]}…")
        # Reset chunks for fresh KB
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

    # Upsert knowledge chunks (textual)
    for ch in KNOWLEDGE_CHUNKS:
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
    print(f"  · {len(KNOWLEDGE_CHUNKS)} chunks de knowledge indexados")

    # Upsert PREMIUM DEMO PROPERTIES (kind=item → renders as cards)
    for p in DEMO_PROPERTIES:
        blob = (
            f"{p['title']}. Localização: {p['location']}. Tipologia {p['typology']}, "
            f"{p['area_m2']}m². {p['description']} Características: {', '.join(p['features'])}. "
            f"Palavras-chave: {p['search_keywords']}"
        )
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": tid,
            "source_id": source_id,
            "kind": "item",
            "title": p["title"],
            "text": blob,
            "meta": {
                "title": p["title"],
                "price": p["price"],
                "image": p["image"],
                "link": p["link"],
                "description": p["description"],
                "location": p["location"],
                "typology": p["typology"],
                "area_m2": p["area_m2"],
                "features": p["features"],
            },
            "indexed_at": now_iso(),
        })
    print(f"  · {len(DEMO_PROPERTIES)} imóveis demo premium indexados como cards")

    await db.data_sources.update_one(
        {"id": source_id},
        {"$set": {"items": len(KNOWLEDGE_CHUNKS) + len(DEMO_PROPERTIES),
                  "chunks": len(KNOWLEDGE_CHUNKS) + len(DEMO_PROPERTIES),
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
        "role": "Consultora digital comercial — Consenso SDR AI",
        "goal": "Educar empresas sobre agentes IA multilingue, qualificar visitantes (nome, empresa, setor, dor, contacto) e converter em pedidos de demonstração personalizada.",
        "tone": "Consultiva, profissional, próxima e orientada a conversão.",
        "rules": (
            "Mensagens curtas (1-2 frases). Português Europeu. Uma pergunta de qualificação por turno. "
            "Adapta linguagem ao perfil (CEO=ROI, IT=integração, Marketing=leads). "
            "Nunca prometas resultados irreais. Modo demo quando pedem 'ver como funciona'. "
            "Captura nome+empresa+email naturalmente antes de propor demo. "
            "Em interesse claro, propõe sempre reunião com a equipa."
        ),
        "system_prompt": SYSTEM_PROMPT,
        "knowledge": KNOWLEDGE_TEXT,
        "default_language": "pt",
        "icebreakers": ICEBREAKERS,
        "welcome_message": WELCOME_MESSAGE,
        "api_provider": "openai",
        "api_key": "",  # Uses OPENAI_API_KEY env var via router
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

    print("\n=== AGENTES NO TENANT ===")
    async for a in db.agents.find({"tenant_id": tid}, {"_id": 0}):
        print(f"  · {a['name']:36} | sources={len(a.get('data_source_ids') or [])} | id={a['id'][:8]}…")


if __name__ == "__main__":
    asyncio.run(run())
