"""News pipeline: fetch RSS feeds → dedupe → LLM summarise → card format.

Sections cover Indian and global markets. Feeds are public RSS endpoints;
add/remove URLs in SECTION_FEEDS freely — everything downstream adapts.
"""
import re
from concurrent.futures import ThreadPoolExecutor

from backend import config
from backend.services import llm_service, scraper
from backend.utils import cache

SECTION_FEEDS: dict[str, list[str]] = {
    "markets": [
        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
        "https://www.livemint.com/rss/markets",
    ],
    "economy": [
        "https://economictimes.indiatimes.com/news/economy/rssfeeds/1373380680.cms",
        "https://www.livemint.com/rss/economy",
    ],
    "banking": [
        "https://economictimes.indiatimes.com/industry/banking/finance/rssfeeds/13358259.cms",
    ],
    "global": [
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    ],
    "commodities": [
        "https://economictimes.indiatimes.com/markets/commodities/rssfeeds/1808152121.cms",
    ],
    "policy": [
        "https://www.livemint.com/rss/politics",
        "https://economictimes.indiatimes.com/news/rssfeeds/1715249553.cms",
    ],
}

SECTION_LABELS = {
    "markets": "Markets", "economy": "Economy", "banking": "Banking & Finance",
    "global": "Global", "commodities": "Commodities", "policy": "Policy & RBI",
}


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower()).strip()


def _fetch_section(section: str) -> list[dict]:
    items: list[dict] = []
    for url in SECTION_FEEDS[section]:
        try:
            items.extend(scraper.fetch_feed(url, limit=10))
        except Exception:
            continue  # one dead feed must not sink the section
    # dedupe by normalised title, keep first (feeds are newest-first)
    seen, unique = set(), []
    for it in items:
        key = _norm_title(it["title"])
        if key and key not in seen:
            seen.add(key)
            unique.append(it)
    unique.sort(key=lambda i: i.get("published") or "", reverse=True)
    unique = unique[:12]
    for it in unique:
        it["section"] = section
        it["section_label"] = SECTION_LABELS[section]
        it["summary"] = llm_service.summarize_news_item(it["title"], it["summary"])
    return unique


def get_news(section: str | None = None, force: bool = False) -> dict:
    """All sections (or one), cached as a single pipeline run."""
    sections = [section] if section and section in SECTION_FEEDS else list(SECTION_FEEDS)

    def run():
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = pool.map(_fetch_section, sections)
        return {s: items for s, items in zip(sections, results)}

    key = "news:" + ",".join(sections)
    if force:
        data = run()
        cache.put(key, data, config.TTL_NEWS)
    else:
        data = cache.get_or_fetch(key, config.TTL_NEWS, run)
    flat = [it for s in sections for it in data.get(s, [])]
    return {"sections": {s: SECTION_LABELS[s] for s in SECTION_FEEDS}, "items": flat,
            "llm": llm_service.get_backend().name}


def get_digest(force: bool = False) -> dict:
    """LLM-written one-paragraph daily market overview."""
    def build():
        news = get_news()
        headlines = [it["title"] for it in news["items"]]
        return {"digest": llm_service.daily_digest(headlines),
                "headline_count": len(headlines)}

    key = "news:digest"
    if force:
        data = build()
        cache.put(key, data, config.TTL_NEWS)
        return data
    return cache.get_or_fetch(key, config.TTL_NEWS, build)


def recent_headlines_text(limit: int = 12) -> str:
    """Compact recent-news context for the chatbot."""
    try:
        items = get_news()["items"][:limit]
    except Exception:
        return ""
    if not items:
        return ""
    return "Recent financial news headlines:\n" + "\n".join(
        f"- [{i['section_label']}] {i['title']}" for i in items
    )
