"""Property Feed externo — importação de imóveis de Idealista/Imovirtual via CSV/XML/Google Sheets.

Configuração por agente em `agent.config.external_feeds = [{type, url, name}]`.
Refresca semanalmente em background. Indexa os imóveis externos como chunks
`kind='external_item'` no MongoDB, ligados ao data_source `external-feed`.

A retrieval (`/app/backend/ai/retrieval.py`) trata estes chunks normalmente — mas
o orchestrator pode escolher mostrar `kind=item` primeiro e `external_item` só
quando os internos não chegam.
"""
import csv
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import List, Optional
import asyncio
import httpx
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# =============================================================================
# PARSERS
# =============================================================================

def parse_csv(text: str) -> List[dict]:
    """Parses CSV with columns: title, price, location, typology, area_m2, image, link, description.
    Returns list of property dicts."""
    items = []
    try:
        reader = csv.DictReader(io.StringIO(text))
        for row in reader:
            t = (row.get("title") or row.get("titulo") or "").strip()
            if not t:
                continue
            items.append({
                "title": t[:200],
                "price": (row.get("price") or row.get("preco") or "").strip()[:60],
                "location": (row.get("location") or row.get("localizacao") or row.get("zona") or "").strip()[:120],
                "typology": (row.get("typology") or row.get("tipologia") or "").strip()[:20],
                "area_m2": _safe_int(row.get("area_m2") or row.get("area")),
                "image": (row.get("image") or row.get("imagem") or "").strip()[:600],
                "link": (row.get("link") or row.get("url") or "").strip()[:600],
                "description": (row.get("description") or row.get("descricao") or "").strip()[:500],
            })
    except Exception as e:
        logger.warning(f"CSV parse error: {e}")
    return items


def parse_xml(text: str) -> List[dict]:
    """Parses an XML feed of properties. Looks for <item>, <property>, <listing> elements
    with child tags: title, price, location, typology, image, link, description."""
    items = []
    try:
        root = ET.fromstring(text)
        for el in root.iter():
            tag = el.tag.lower().split("}")[-1]
            if tag not in {"item", "property", "listing", "imovel", "anuncio"}:
                continue
            d = {}
            for c in el:
                ctag = c.tag.lower().split("}")[-1]
                if c.text:
                    d[ctag] = c.text.strip()
            t = d.get("title") or d.get("titulo") or d.get("name") or ""
            if not t:
                continue
            items.append({
                "title": t[:200],
                "price": (d.get("price") or d.get("preco") or "")[:60],
                "location": (d.get("location") or d.get("zona") or d.get("localizacao") or "")[:120],
                "typology": (d.get("typology") or d.get("tipologia") or "")[:20],
                "area_m2": _safe_int(d.get("area_m2") or d.get("area")),
                "image": (d.get("image") or d.get("imagem") or d.get("photo") or "")[:600],
                "link": (d.get("link") or d.get("url") or "")[:600],
                "description": (d.get("description") or d.get("descricao") or "")[:500],
            })
    except Exception as e:
        logger.warning(f"XML parse error: {e}")
    return items


def parse_gsheet(text_or_url: str) -> List[dict]:
    """Google Sheets quando publicado como CSV (File → Share → Publish to web → CSV).
    Aceita o conteúdo já descarregado em CSV (igual a parse_csv)."""
    return parse_csv(text_or_url)


def _safe_int(value) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(re.sub(r"[^\d]", "", str(value)) or 0) or None
    except (ValueError, TypeError):
        return None


# =============================================================================
# FETCH + INDEX
# =============================================================================

async def fetch_feed(feed: dict) -> List[dict]:
    """Descarrega e parseia um feed externo. Retorna lista de imóveis."""
    url = feed.get("url")
    ftype = (feed.get("type") or "csv").lower()
    if not url:
        return []

    # Google Sheets: garantir o suffix /export?format=csv se for um sheet
    if ftype == "gsheet":
        if "/edit" in url:
            url = url.split("/edit")[0] + "/export?format=csv"
        ftype = "csv"

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "ConsensoPlus/1.0"})
            r.raise_for_status()
            text = r.text
    except Exception as e:
        logger.warning(f"Failed to fetch feed {url}: {e}")
        return []

    if ftype == "csv":
        return parse_csv(text)
    if ftype == "xml":
        return parse_xml(text)
    return []


async def index_external_feed(db, tenant_id: str, agent_id: str, feed: dict) -> dict:
    """Faz fetch+index de um feed externo. Substitui chunks anteriores deste feed.
    Retorna stats {ok, items, source_id}."""
    items = await fetch_feed(feed)
    if not items:
        return {"ok": False, "items": 0, "error": "Sem imóveis no feed"}

    feed_name = feed.get("name") or f"Feed externo · {feed.get('type', 'csv').upper()}"
    source_id_key = f"external-feed:{agent_id}:{feed.get('url')[:60]}"

    # Find or create the data_source
    existing = await db.data_sources.find_one(
        {"tenant_id": tenant_id, "source_key": source_id_key}, {"_id": 0}
    )
    if existing:
        source_id = existing["id"]
        await db.data_chunks.delete_many({"source_id": source_id})
    else:
        source_id = str(uuid.uuid4())
        await db.data_sources.insert_one({
            "id": source_id,
            "tenant_id": tenant_id,
            "name": feed_name,
            "type": "external_feed",
            "url": feed.get("url"),
            "source_key": source_id_key,
            "agent_id": agent_id,
            "items": len(items),
            "chunks": len(items),
            "indexed_at": now_iso(),
            "created_at": now_iso(),
        })

    # Insert chunks (kind=external_item)
    for p in items:
        keywords = (
            f"{p.get('typology', '')} {p.get('location', '')} "
            f"externo terceiros idealista imovirtual portal externo "
            f"imóvel imoveis casa apartamento"
        )
        blob = (
            f"[EXTERNO] {p.get('title', '')}. {p.get('location', '')}. "
            f"{p.get('typology', '')}, {p.get('area_m2') or '—'}m². "
            f"{p.get('description', '')} Palavras-chave: {keywords}"
        )
        await db.data_chunks.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "source_id": source_id,
            "agent_id": agent_id,
            "kind": "external_item",  # IMPORTANTE: distingue dos `item` internos
            "title": p.get("title"),
            "text": blob,
            "meta": {
                "title": p.get("title"),
                "price": p.get("price"),
                "image": p.get("image"),
                "link": p.get("link"),
                "description": p.get("description"),
                "location": p.get("location"),
                "typology": p.get("typology"),
                "area_m2": p.get("area_m2"),
                "external": True,
                "feed_name": feed_name,
            },
            "indexed_at": now_iso(),
        })

    # Update data source stats
    await db.data_sources.update_one(
        {"id": source_id},
        {"$set": {"items": len(items), "chunks": len(items), "indexed_at": now_iso()}},
    )

    # Link to agent (no data_source_ids if missing)
    await db.agents.update_one(
        {"id": agent_id},
        {"$addToSet": {"data_source_ids": source_id}},
    )

    return {"ok": True, "items": len(items), "source_id": source_id, "feed_name": feed_name}


async def refresh_all_feeds(db) -> dict:
    """Corre todos os feeds configurados em agent.config.external_feeds[]."""
    total = {"agents": 0, "feeds": 0, "items": 0, "errors": 0}
    async for agent in db.agents.find({"active": True}, {"_id": 0}):
        feeds = (agent.get("config") or {}).get("external_feeds") or []
        if not feeds:
            continue
        total["agents"] += 1
        for feed in feeds:
            total["feeds"] += 1
            try:
                r = await index_external_feed(db, agent["tenant_id"], agent["id"], feed)
                if r.get("ok"):
                    total["items"] += r["items"]
                else:
                    total["errors"] += 1
            except Exception as e:
                logger.warning(f"Feed refresh error for agent {agent['id']}: {e}")
                total["errors"] += 1
    logger.info(f"Feed refresh complete: {total}")
    return total


async def scheduler_loop(db, interval_seconds: int = 7 * 24 * 3600):
    """Loop semanal. Em produção, opcionalmente substituir por cron K8s."""
    logger.info(f"Property feed scheduler started (interval={interval_seconds}s)")
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            await refresh_all_feeds(db)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.warning(f"Feed scheduler error: {e}")
            await asyncio.sleep(3600)
