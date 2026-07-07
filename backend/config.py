"""Central configuration: environment variables, constants, index definitions.

All API keys and tunables are read from the environment (.env supported).
See .env.example at the repo root for the full list.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DUMMY_DIR = DATA_DIR / "dummy"
CACHE_DIR = DATA_DIR / "cache"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

for _d in (DUMMY_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# -- LLM configuration ---------------------------------------------------------
# LLM_BACKEND: "anthropic" | "ollama" | "none"
# "none" degrades gracefully to extractive (non-LLM) summaries so the app
# always runs, even with no key and no local model.
LLM_BACKEND = os.getenv("LLM_BACKEND", "none").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# Fast model for card summaries, deeper model for chat / investment briefs.
OLLAMA_FAST_MODEL = os.getenv("OLLAMA_FAST_MODEL", "llama3.2:3b")
OLLAMA_DEEP_MODEL = os.getenv("OLLAMA_DEEP_MODEL", "llama3.2:3b")

# -- Cache TTLs (seconds) ------------------------------------------------------
TTL_QUOTES = int(os.getenv("TTL_QUOTES", "600"))          # constituent quotes
TTL_HISTORY = int(os.getenv("TTL_HISTORY", "3600"))        # price history
TTL_FUNDAMENTALS = int(os.getenv("TTL_FUNDAMENTALS", "21600"))
TTL_NEWS = int(os.getenv("TTL_NEWS", "1800"))              # news pipeline
TTL_LLM = int(os.getenv("TTL_LLM", "21600"))               # LLM summaries

# -- Index universe -------------------------------------------------------------
# "static" holds index-level valuation metrics (P/E, P/B, dividend yield) that
# NSE publishes daily but Yahoo does not expose for indices. Swap these for a
# live NSE fetch in services/market_data.py without touching the frontend.
NIFTY50_CONSTITUENTS = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "BHARTIARTL", "ITC",
    "SBIN", "HINDUNILVR", "LT", "KOTAKBANK", "AXISBANK", "BAJFINANCE",
    "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN", "ULTRACEMCO", "NESTLEIND",
    "WIPRO", "M&M", "NTPC", "HCLTECH", "POWERGRID", "TATAMOTORS", "TATASTEEL",
    "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV", "ONGC", "GRASIM",
    "JSWSTEEL", "HINDALCO", "DRREDDY", "CIPLA", "TECHM", "INDUSINDBK",
    "EICHERMOT", "APOLLOHOSP", "BRITANNIA", "TATACONSUM", "HEROMOTOCO",
    "BAJAJ-AUTO", "SBILIFE", "HDFCLIFE", "LTIM", "SHRIRAMFIN", "BPCL", "TRENT",
]

INDICES = {
    "nifty50": {
        "name": "NIFTY 50",
        "yahoo": "^NSEI",
        "color": "#2A78D6",
        "description": "India's benchmark large-cap index of 50 blue-chip companies.",
        "constituents": NIFTY50_CONSTITUENTS,
        "static": {"pe": 22.4, "pb": 3.6, "div_yield": 1.21, "market_cap_cr": 19500000},
    },
    "niftybank": {
        "name": "NIFTY Bank",
        "yahoo": "^NSEBANK",
        "color": "#0E9866",
        "description": "The 12 most liquid and large-capitalised Indian banking stocks.",
        "constituents": [
            "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK",
            "INDUSINDBK", "BANKBARODA", "PNB", "IDFCFIRSTB", "AUBANK",
            "FEDERALBNK", "CANBK",
        ],
        "static": {"pe": 15.1, "pb": 2.4, "div_yield": 0.98, "market_cap_cr": 4200000},
    },
    "niftyit": {
        "name": "NIFTY IT",
        "yahoo": "^CNXIT",
        "color": "#4A3AA7",
        "description": "The 10 largest Indian information-technology companies.",
        "constituents": [
            "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM",
            "LTIM", "PERSISTENT", "COFORGE", "MPHASIS", "LTTS",
        ],
        "static": {"pe": 28.7, "pb": 7.1, "div_yield": 2.05, "market_cap_cr": 3100000},
    },
    "cpse": {
        "name": "CPSE",
        "yahoo": "CPSEETF.NS",
        "color": "#B8860B",
        "description": "Central Public Sector Enterprises ETF - large state-owned energy and infrastructure companies.",
        "constituents": [
            "NTPC", "POWERGRID", "ONGC", "COALINDIA", "BEL",
            "NHPC", "OIL", "SJVN", "NBCC", "NLCINDIA", "COCHINSHIP",
        ],
        "static": {"pe": 11.2, "pb": 2.1, "div_yield": 3.42, "market_cap_cr": 2350000},
    },
    "bharat22": {
        "name": "Bharat 22",
        "yahoo": "ICICIB22.NS",
        "color": "#C23D6F",
        "description": "Bharat 22 ETF - a diversified basket of 22 PSU, PSB and government-holding companies.",
        "constituents": [
            "ITC", "LT", "SBIN", "AXISBANK", "NTPC", "ONGC", "POWERGRID",
            "COALINDIA", "IOC", "BPCL", "GAIL", "BEL", "NATIONALUM",
            "ENGINERSIN", "NBCC", "SJVN",
        ],
        "static": {"pe": 13.6, "pb": 2.8, "div_yield": 2.71, "market_cap_cr": 2980000},
    },
}

INDEX_ORDER = ["nifty50", "niftybank", "niftyit", "cpse", "bharat22"]


def yahoo_symbol(nse_ticker: str) -> str:
    """Map an NSE ticker to its Yahoo Finance symbol."""
    return f"{nse_ticker}.NS"


def find_index_of_company(symbol: str) -> str | None:
    """Return the first index id containing this company, if any."""
    for idx_id, idx in INDICES.items():
        if symbol in idx["constituents"]:
            return idx_id
    return None
