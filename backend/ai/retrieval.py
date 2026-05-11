"""Data source ingestion + simple keyword retrieval for the AI agent."""
import re
import uuid
import logging
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _chunk(text: str, size: int = 800) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    out = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        # try to cut on sentence
        if end < len(text):
            dot = text.rfind(". ", start, end)
            if dot > start + 200:
                end = dot + 1
        out.append(text[start:end].strip())
        start = end
    return out


def scrape_url(url: str, max_pages: int = 1) -> Dict[str, Any]:
    """Scrape a URL. Returns {title, text, items: [{title, price, image, link, description}]}"""
    headers = {"User-Agent": "ConsensoPlus/1.0 (+https://consenso-agents.com)"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    for t in soup(["script", "style", "noscript"]):
        t.decompose()

    title = (soup.title.string or "").strip() if soup.title else url
    text = soup.get_text(separator="\n", strip=True)

    # Heuristic: detect item/product/listing cards
    items = []
    candidates = soup.find_all(
        ["article", "li", "div"],
        class_=re.compile(r"(card|item|product|listing|property|result)", re.I),
        limit=40,
    )
    for c in candidates:
        t_el = c.find(["h1", "h2", "h3", "h4", "a"])
        if not t_el:
            continue
        t_title = t_el.get_text(strip=True)[:140]
        if not t_title or len(t_title) < 3:
            continue
        link = ""
        a = c.find("a", href=True)
        if a:
            href = a["href"]
            if href.startswith("http"):
                link = href
            else:
                # naive relative join
                from urllib.parse import urljoin
                link = urljoin(url, href)
        img = ""
        i = c.find("img")
        if i:
            img = i.get("src") or i.get("data-src") or ""
            if img and not img.startswith("http"):
                from urllib.parse import urljoin
                img = urljoin(url, img)
        price_m = re.search(r"(€|£|\$|R\$|USD|EUR)\s?[\d.,]+|[\d.,]+\s?(€|EUR|USD)", c.get_text(" ", strip=True))
        price = price_m.group(0) if price_m else ""
        desc = c.get_text(" ", strip=True)[:200]
        items.append({
            "title": t_title,
            "link": link,
            "image": img,
            "price": price,
            "description": desc,
        })

    # Deduplicate items by title
    seen = set()
    dedup = []
    for it in items:
        if it["title"] in seen:
            continue
        seen.add(it["title"])
        dedup.append(it)

    return {"title": title, "text": text[:50000], "items": dedup[:30]}


def build_chunks(source_id: str, tenant_id: str, title: str, text: str, items: List[dict]) -> List[dict]:
    chunks = []
    for c in _chunk(text):
        chunks.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "source_id": source_id,
            "kind": "text",
            "text": c,
            "meta": {"source_title": title},
        })
    for it in items:
        blob = f"{it.get('title','')}\n{it.get('description','')}\nPrice: {it.get('price','')}"
        chunks.append({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "source_id": source_id,
            "kind": "item",
            "text": blob,
            "meta": it,
        })
    return chunks


def score_chunk(query_terms: List[str], chunk_text: str) -> float:
    low = chunk_text.lower()
    return sum(1.0 for t in query_terms if t in low)


async def retrieve(db, tenant_id: str, query: str, k: int = 6, source_ids: List[str] = None) -> List[dict]:
    """Keyword retrieval over the tenant's indexed chunks. If source_ids is provided,
    only search those sources (per-agent retrieval).

    Priority: internal `kind=item` first, then `knowledge`, then `external_item` (only
    when internal items don't fill the slots). This ensures the agent shows the
    agency's own portfolio before falling back to Idealista/Imovirtual feeds."""
    stop_pt = {"a", "o", "as", "os", "de", "do", "da", "em", "e", "ou", "no", "na", "um", "uma", "para", "por", "que", "com", "se", "é"}
    raw_terms = re.findall(r"[\w\u00C0-\u017F]+", query.lower())
    terms = [t for t in raw_terms if (len(t) >= 2 and t not in stop_pt)]
    if not terms:
        return []
    mongo_q = {"tenant_id": tenant_id}
    if source_ids:
        mongo_q["source_id"] = {"$in": source_ids}
    cur = db.data_chunks.find(mongo_q, {"_id": 0}).limit(2000)
    docs = await cur.to_list(2000)
    scored = [(score_chunk(terms, d["text"]), d) for d in docs]
    scored = [s for s in scored if s[0] > 0]

    # Sort key: (kind_priority, -score)
    # 0 = item (internal portfolio), 1 = knowledge, 2 = external_item (3rd-party feeds), 3 = text/other
    def _kind_prio(d):
        k = d.get("kind")
        if k == "item":
            return 0
        if k == "knowledge":
            return 1
        if k == "external_item":
            return 2
        return 3

    scored.sort(key=lambda x: (_kind_prio(x[1]), -x[0]))

    # Count internal items
    internal_items = [d for _, d in scored if d.get("kind") == "item"]
    others = [d for _, d in scored if d.get("kind") != "external_item"]
    externals = [d for _, d in scored if d.get("kind") == "external_item"]

    # Fill: internal items first, then knowledge/text, then external items
    # ONLY include external if internal items < 2 (i.e., portfolio doesn't have enough)
    result = others[:k]
    if len([d for d in result if d.get("kind") == "item"]) < 2 and externals:
        # Add up to (k - len(result)) externals, ensuring at least 1 if portfolio is weak
        slots_left = max(k - len(result), 1)
        for e in externals[:slots_left]:
            result.append(e)
            if len(result) >= k:
                break

    return result[:k]
