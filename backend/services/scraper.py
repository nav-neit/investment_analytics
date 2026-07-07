"""Web scraping utilities: RSS/news fetching for companies and market feeds.

Uses Google News RSS (public, keyless) for company-specific news and plain
requests + feedparser for outlet feeds. All HTML in summaries is stripped
with BeautifulSoup before anything reaches the LLM or the frontend.
"""
import html as html_mod
import time
from urllib.parse import quote_plus

import requests

try:
    import feedparser
except ImportError:
    feedparser = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

from backend import config
from backend.utils import cache

HEADERS = {"User-Agent": "Mozilla/5.0 (QuantArtha internal research tool)"}
REQUEST_TIMEOUT = 12


def strip_html(text: str) -> str:
    if not text:
        return ""
    if BeautifulSoup:
        text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    # sources sometimes double-encode entities (e.g. "S&amp;P" survives one decode)
    return html_mod.unescape(text)


def fetch_feed(url: str, limit: int = 15) -> list[dict]:
    """Fetch and normalise one RSS/Atom feed into a list of item dicts."""
    if feedparser is None:
        return []
    resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    items = []
    for entry in parsed.entries[:limit]:
        published = None
        for attr in ("published_parsed", "updated_parsed"):
            t = getattr(entry, attr, None)
            if t:
                published = time.strftime("%Y-%m-%dT%H:%M:%SZ", t)
                break
        items.append({
            "title": strip_html(getattr(entry, "title", "")),
            "summary": strip_html(getattr(entry, "summary", ""))[:600],
            "link": getattr(entry, "link", ""),
            "source": strip_html(parsed.feed.get("title", "") or ""),
            "published": published,
        })
    return [i for i in items if i["title"]]


def company_news(symbol: str, name: str | None = None, limit: int = 10) -> list[dict]:
    """Latest news for one company via Google News RSS, cached."""
    query = f"{name or symbol} NSE stock"
    url = ("https://news.google.com/rss/search?q="
           f"{quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en")

    def fetch():
        items = fetch_feed(url, limit=limit)
        # Google News titles end with " - Source"; split it out.
        for it in items:
            if " - " in it["title"]:
                title, _, src = it["title"].rpartition(" - ")
                it["title"], it["source"] = title, src
        return items

    try:
        return cache.get_or_fetch(f"conews:{symbol}", config.TTL_NEWS, fetch) or []
    except Exception:
        return []
