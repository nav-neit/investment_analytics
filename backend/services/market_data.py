"""Market data service: prices, history and fundamentals for indices & stocks.

Primary source is Yahoo Finance via yfinance; every fetch is cached on disk
(backend/data/cache) and falls back to a deterministic synthetic series when
the network or Yahoo is unavailable, so the whole app stays demo-able offline.
Payloads carry a "source" field ("live" | "synthetic") so the UI can flag it.

To swap in NSE's official APIs later, replace the _fetch_* internals — the
public function signatures (and therefore the REST contract) stay the same.
"""
import datetime as dt
import math
import random
from concurrent.futures import ThreadPoolExecutor

from backend import config
from backend.utils import cache

try:
    import yfinance as yf
except ImportError:  # keeps the app importable before deps are installed
    yf = None

RANGE_TO_PERIOD = {"1M": "1mo", "6M": "6mo", "1Y": "1y", "5Y": "5y", "10Y": "10y", "MAX": "max"}


# ── synthetic fallback ─────────────────────────────────────────────────────────
def _seed_base(symbol: str) -> float:
    rng = random.Random(symbol)
    return rng.uniform(80, 4000)


def _synthetic_history(symbol: str, days: int) -> dict:
    """Deterministic random-walk OHLCV series seeded by symbol."""
    rng = random.Random(f"{symbol}:{days}")
    price = _seed_base(symbol)
    drift = rng.uniform(0.0002, 0.0008)
    vol = rng.uniform(0.008, 0.02)
    end = dt.date.today()
    dates, closes, volumes = [], [], []
    d = end - dt.timedelta(days=int(days * 1.45))  # skip weekends
    while d <= end:
        if d.weekday() < 5:
            price *= math.exp(rng.gauss(drift, vol))
            dates.append(d.isoformat())
            closes.append(round(price, 2))
            volumes.append(int(rng.uniform(0.5, 3.0) * 1e6))
        d += dt.timedelta(days=1)
    return {"dates": dates[-days:], "close": closes[-days:], "volume": volumes[-days:],
            "source": "synthetic"}


# ── history ────────────────────────────────────────────────────────────────────
def _fetch_history(yahoo_sym: str, period: str) -> dict | None:
    if yf is None:
        return None
    hist = yf.Ticker(yahoo_sym).history(period=period, auto_adjust=True)
    if hist is None or hist.empty:
        return None
    hist = hist.dropna(subset=["Close"])
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
        "close": [round(float(c), 2) for c in hist["Close"]],
        "volume": [int(v) if v == v else 0 for v in hist["Volume"]],
        "source": "live",
    }


def get_history(yahoo_sym: str, range_key: str = "1Y") -> dict:
    period = RANGE_TO_PERIOD.get(range_key.upper(), "1y")
    key = f"hist:{yahoo_sym}:{period}"
    try:
        data = cache.get_or_fetch(key, config.TTL_HISTORY, lambda: _fetch_history(yahoo_sym, period))
        if data:
            return data
    except Exception:
        pass
    days = {"1mo": 22, "6mo": 130, "1y": 252, "5y": 1260, "10y": 2520, "max": 2520}[period]
    return _synthetic_history(yahoo_sym, days)


def _cagr(closes: list[float], dates: list[str], years: int) -> float | None:
    if not closes:
        return None
    cutoff = (dt.date.today() - dt.timedelta(days=int(years * 365.25))).isoformat()
    start_i = next((i for i, d in enumerate(dates) if d >= cutoff), None)
    if start_i is None or start_i >= len(closes) - 20:
        return None  # series doesn't reach back far enough
    start, end = closes[start_i], closes[-1]
    if start <= 0:
        return None
    return round(((end / start) ** (1 / years) - 1) * 100, 2)


# ── index overview (Level 1) ──────────────────────────────────────────────────
def _index_overview(idx_id: str) -> dict:
    idx = config.INDICES[idx_id]
    hist = get_history(idx["yahoo"], "10Y")
    closes, dates = hist["close"], hist["dates"]
    year_ago = (dt.date.today() - dt.timedelta(days=365)).isoformat()
    yr_slice = [c for c, d in zip(closes, dates) if d >= year_ago] or closes[-252:]
    current = closes[-1] if closes else None
    prev = closes[-2] if len(closes) > 1 else current
    return {
        "id": idx_id,
        "name": idx["name"],
        "description": idx["description"],
        "color": idx["color"],
        "price": current,
        "day_change_pct": round((current - prev) / prev * 100, 2) if current and prev else 0,
        "high_52w": round(max(yr_slice), 2) if yr_slice else None,
        "low_52w": round(min(yr_slice), 2) if yr_slice else None,
        "market_cap_cr": idx["static"]["market_cap_cr"],
        "pe": idx["static"]["pe"],
        "pb": idx["static"]["pb"],
        "div_yield": idx["static"]["div_yield"],
        "cagr_1y": _cagr(closes, dates, 1),
        "cagr_5y": _cagr(closes, dates, 5),
        "cagr_10y": _cagr(closes, dates, 10),
        "sparkline": closes[-60:],
        "source": hist["source"],
        "constituent_count": len(idx["constituents"]),
    }


def get_indices_overview() -> list[dict]:
    with ThreadPoolExecutor(max_workers=5) as pool:
        return list(pool.map(_index_overview, config.INDEX_ORDER))


# ── constituents (Level 2) ─────────────────────────────────────────────────────
def _fetch_quote(symbol: str) -> dict | None:
    if yf is None:
        return None
    t = yf.Ticker(config.yahoo_symbol(symbol))
    info = t.info
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    if price is None:
        return None
    prev = info.get("previousClose") or price
    return {
        "symbol": symbol,
        "name": info.get("shortName") or symbol,
        "price": round(float(price), 2),
        "day_change_pct": round((price - prev) / prev * 100, 2) if prev else 0,
        "market_cap_cr": round(info.get("marketCap", 0) / 1e7, 0),  # ₹ → ₹ Cr
        "pe": round(info["trailingPE"], 1) if info.get("trailingPE") else None,
        "pb": round(info["priceToBook"], 1) if info.get("priceToBook") else None,
        "div_yield": round(info["dividendYield"], 2) if info.get("dividendYield") else None,
        "roe": round(info["returnOnEquity"] * 100, 1) if info.get("returnOnEquity") else None,
        "high_52w": info.get("fiftyTwoWeekHigh"),
        "low_52w": info.get("fiftyTwoWeekLow"),
        "sector": info.get("sector"),
        "source": "live",
    }


def _synthetic_quote(symbol: str) -> dict:
    rng = random.Random(f"q:{symbol}")
    price = round(_seed_base(symbol), 2)
    return {
        "symbol": symbol, "name": symbol.title(),
        "price": price,
        "day_change_pct": round(rng.uniform(-2.5, 2.5), 2),
        "market_cap_cr": round(rng.uniform(20000, 1500000), 0),
        "pe": round(rng.uniform(8, 45), 1),
        "pb": round(rng.uniform(1, 12), 1),
        "div_yield": round(rng.uniform(0.2, 4.5), 2),
        "roe": round(rng.uniform(5, 30), 1),
        "high_52w": round(price * rng.uniform(1.05, 1.4), 2),
        "low_52w": round(price * rng.uniform(0.6, 0.95), 2),
        "sector": None,
        "source": "synthetic",
    }


def get_quote(symbol: str) -> dict:
    key = f"quote:{symbol}"
    try:
        q = cache.get_or_fetch(key, config.TTL_QUOTES, lambda: _fetch_quote(symbol))
        if q:
            return q
    except Exception:
        pass
    return _synthetic_quote(symbol)


def get_constituents(idx_id: str) -> list[dict]:
    symbols = config.INDICES[idx_id]["constituents"]
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(get_quote, symbols))


# ── company deep dive (Level 3) ────────────────────────────────────────────────
def _fetch_profile(symbol: str) -> dict | None:
    if yf is None:
        return None
    info = yf.Ticker(config.yahoo_symbol(symbol)).info
    if not info.get("regularMarketPrice") and not info.get("currentPrice"):
        return None
    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName") or symbol,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "summary": (info.get("longBusinessSummary") or "")[:900],
        "website": info.get("website"),
        "metrics": {
            "eps": info.get("trailingEps"),
            "book_value": info.get("bookValue"),
            "profit_margin_pct": round(info["profitMargins"] * 100, 1) if info.get("profitMargins") else None,
            "revenue_growth_pct": round(info["revenueGrowth"] * 100, 1) if info.get("revenueGrowth") else None,
            "debt_to_equity": info.get("debtToEquity"),
            "beta": info.get("beta"),
            "avg_volume": info.get("averageVolume"),
        },
        "source": "live",
    }


def get_company_profile(symbol: str) -> dict:
    key = f"profile:{symbol}"
    profile = None
    try:
        profile = cache.get_or_fetch(key, config.TTL_FUNDAMENTALS, lambda: _fetch_profile(symbol))
    except Exception:
        pass
    if not profile:
        rng = random.Random(f"p:{symbol}")
        profile = {
            "symbol": symbol, "name": symbol.title(), "sector": None, "industry": None,
            "summary": "", "website": None,
            "metrics": {
                "eps": round(rng.uniform(5, 120), 1), "book_value": round(rng.uniform(50, 900), 1),
                "profit_margin_pct": round(rng.uniform(4, 28), 1),
                "revenue_growth_pct": round(rng.uniform(-5, 25), 1),
                "debt_to_equity": round(rng.uniform(0, 180), 1), "beta": round(rng.uniform(0.5, 1.8), 2),
                "avg_volume": int(rng.uniform(1e5, 2e7)),
            },
            "source": "synthetic",
        }
    profile["quote"] = get_quote(symbol)
    profile["index"] = config.find_index_of_company(symbol)
    return profile


def get_company_history(symbol: str, range_key: str = "1Y") -> dict:
    return get_history(config.yahoo_symbol(symbol), range_key)


# ── snapshot for chatbot context ───────────────────────────────────────────────
def market_snapshot_text() -> str:
    """Compact plain-text market snapshot injected into LLM chat context."""
    lines = []
    for o in get_indices_overview():
        lines.append(
            f"{o['name']}: {o['price']} ({o['day_change_pct']:+.2f}% today), "
            f"P/E {o['pe']}, P/B {o['pb']}, 1Y CAGR {o['cagr_1y']}%, 5Y CAGR {o['cagr_5y']}%"
        )
    return "Current index snapshot:\n" + "\n".join(lines)
