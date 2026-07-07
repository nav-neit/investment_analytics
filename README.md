# QuantArtha — Financial Analytics & Intelligence Platform

Internal investment-team dashboard tracking five Indian ETF indices —
**NIFTY 50, NIFTY Bank, NIFTY IT, CPSE, Bharat 22** — with a drill-down
screener, data-science model analytics, an AI-summarised news hub, a
context-aware assistant, and a signals/alerts module.

- **Frontend:** pure HTML/CSS/vanilla JS + Chart.js (CDN). No frameworks.
- **Backend:** Python, FastAPI + Uvicorn. All data fetching, scraping, LLM
  calls and computation happen server-side; the frontend only consumes REST.

## Quick start

```bash
# 1. install dependencies (Python 3.11+)
pip install -r backend/requirements.txt

# 2. configure (optional — the app runs with zero config)
copy .env.example .env        # then edit as needed

# 3. run — single command, serves API + frontend
uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000**. Interactive API docs at `/docs`.

With no configuration the app still fully works:

- Market data comes from Yahoo Finance (`yfinance`) and is disk-cached; if the
  network is down, endpoints fall back to deterministic synthetic series and
  the UI shows a red **demo data** badge instead of **live**.
- LLM features degrade to extractive summaries with a hint to configure a backend.

## Environment variables (`.env`)

| Variable | Values | Purpose |
|---|---|---|
| `LLM_BACKEND` | `anthropic` \| `ollama` \| `none` | selects the LLM engine (default `none`) |
| `ANTHROPIC_API_KEY` | key | hosted API (when `anthropic`) |
| `ANTHROPIC_MODEL` | model id | default `claude-haiku-4-5-20251001` |
| `OLLAMA_HOST` | url | default `http://localhost:11434` |
| `OLLAMA_FAST_MODEL` | model | fast summariser, e.g. `llama3.2:3b` |
| `OLLAMA_DEEP_MODEL` | model | analysis/chat model, e.g. a finance-tuned 8B |
| `TTL_*` | seconds | cache TTL overrides (see `.env.example`) |

### Using local models (Ollama)

```bash
ollama pull llama3.2:3b            # fast summarisation
# optional deeper model for chat & investment briefs, e.g. an 8B finance tune
echo LLM_BACKEND=ollama >> .env
```

`services/llm_service.py` defines one common interface (`complete(system,
messages)`); `OLLAMA_FAST_MODEL` handles news cards/digests, `OLLAMA_DEEP_MODEL`
handles chat and company briefs. Adding another provider = one new backend class.

## Project layout

```
frontend/            static UI (served by FastAPI at /)
  index.html         Page 1 — Index Screener (3 drill-down levels via URL hash)
  models.html        Page 2 — Model Analytics + Signals & Alerts panel
  news.html          Page 3 — Market News hub
  assistant.html     full-page AI assistant (also a slide-out panel everywhere)
  css/ js/           theme tokens, styles, page scripts, shared API client
backend/
  main.py            FastAPI app: routers, CORS, static serving
  config.py          env config, cache TTLs, index definitions & constituents
  routers/           /api/indices /api/companies /api/models /api/news /api/chat /api/alerts
  services/          market_data (yfinance), scraper (RSS), news_aggregator,
                     llm_service (pluggable backends + chat context), alerts
  data/dummy/        generated model outputs (Page 2) + generator script
  data/cache/        disk cache for API/scrape/LLM responses
  utils/cache.py     TTL file cache (serves stale data if a source errors)
```

## Swapping dummy model data for real models

Page 2 is fed entirely by `backend/routers/models.py`, which loads
`backend/data/dummy/model_outputs.json` via `backend/data/dummy/generate.py`.
The JSON schema is the contract:

1. Point `_load()` in `routers/models.py` at your real pipeline (or overwrite
   the JSON file on each model run).
2. Keep the keys: `months`, `growth`, `deltas`, `comparison`, `allocations`,
   `summary` — the REST endpoints and frontend need no changes.
3. Regenerate demo data anytime: `python -m backend.data.dummy.generate`.

The same applies to market data: `services/market_data.py` isolates all
Yahoo/NSE specifics; replace the `_fetch_*` internals to switch to official
NSE endpoints without touching routers or frontend.

## Feature notes

- **Screener drill-down:** overview table → click index → constituents +
  price/P-E charts (1M/6M/1Y/5Y toggles) → click company → fundamentals,
  price/volume charts, scraped news, and an LLM investment brief.
  The index P/E trend is a price-proxy placeholder until an NSE valuation
  history source is wired in.
- **News pipeline:** RSS fetch (ET, Mint, BBC, CNBC…) → title dedupe → LLM
  card summaries + one-paragraph daily digest; sections: Markets, Economy,
  Banking & Finance, Global, Commodities, Policy & RBI. `↻ Refresh` busts the cache.
- **Assistant:** `/api/chat` injects live platform context (index snapshot +
  recent headlines) through a pluggable provider registry
  (`llm_service.register_context_provider`) — future knowledge-repo sources
  plug in there. Conversations persist per browser session and export as `.md`.
- **Signals & Alerts:** define threshold rules (P/E, P/B, dividend yield,
  price, day change %, model allocation shift) on the Model Analytics page.
  Rules are evaluated on every page load / data refresh; triggers land in the
  navbar 🔔 with history, at most one fire per rule per day.
  A standalone HTML **weekly digest** (model summary + top news) is at
  `/api/alerts/digest` — print to PDF for meetings.
- **Caching:** all external calls go through `utils/cache.py` (file-backed,
  per-key TTLs; stale-if-error). Delete `backend/data/cache/` to reset.

*Internal tool. Nothing here is investment advice.*
