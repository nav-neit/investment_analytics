"""File-backed JSON cache with per-entry TTLs.

Keeps scraped / API data on disk under backend/data/cache so restarts don't
re-hit rate-limited sources. Values must be JSON-serialisable.
"""
import hashlib
import json
import time
from typing import Any, Callable

from backend.config import CACHE_DIR


def _path(key: str):
    digest = hashlib.sha1(key.encode()).hexdigest()[:16]
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)[:60]
    return CACHE_DIR / f"{safe}.{digest}.json"


def get(key: str) -> Any | None:
    p = _path(key)
    if not p.exists():
        return None
    try:
        entry = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if entry["expires"] < time.time():
        return None
    return entry["value"]


def put(key: str, value: Any, ttl: int) -> None:
    entry = {"expires": time.time() + ttl, "cached_at": time.time(), "value": value}
    _path(key).write_text(json.dumps(entry), encoding="utf-8")


def get_or_fetch(key: str, ttl: int, fetch: Callable[[], Any]) -> Any:
    """Return cached value or call fetch(), caching a non-None result.

    If fetch() raises but a stale cache entry exists, serve the stale copy —
    a slightly old quote beats a 500.
    """
    cached = get(key)
    if cached is not None:
        return cached
    try:
        value = fetch()
    except Exception:
        stale = _stale(key)
        if stale is not None:
            return stale
        raise
    if value is not None:
        put(key, value, ttl)
    return value


def _stale(key: str) -> Any | None:
    p = _path(key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))["value"]
    except (json.JSONDecodeError, OSError, KeyError):
        return None
