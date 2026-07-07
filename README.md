# VittaLens — Financial Analytics & Intelligence Platform

Internal investment-team dashboard tracking five Indian ETF indices —
**NIFTY 50, NIFTY Bank, NIFTY IT, CPSE, Bharat 22** — with a drill-down
screener, data-science model analytics, an AI-summarised news hub, a
context-aware assistant, and a signals/alerts module.

- **Frontend:** pure HTML/CSS/vanilla JS + Chart.js (CDN). No frameworks.
- **Backend:** Python, FastAPI + Uvicorn. All data fetching, scraping, LLM
  calls and computation happen server-side; the frontend only consumes REST.

## Quick start (one command)

The start scripts create a virtual environment on first run, install
dependencies, and launch the server on **port 8030**:

```bash
./start_server.sh        # Linux / macOS server
start_server.bat         # Windows
```

Open **http://127.0.0.1:8030** (or `http://<server-ip>:8030` when hosted).
Interactive API docs at `/docs`.

## Deploy with Docker (recommended)

No Python or venv needed on the server — just Docker. From the project root:

```bash
docker compose up -d --build
```

That single command builds the image, starts the container on port 8030 with
auto-restart, and mounts a named volume so runtime data (API cache, alert
rules & history) survives rebuilds. Open `http://<server-ip>:8030`.

Configuration is optional: if a `.env` file exists next to
`docker-compose.yml` (copy it from `.env.example`), Compose picks the values
up automatically; without one, sensible defaults apply (LLM features off).
After changing `.env` or code, redeploy with the same command:

```bash
docker compose up -d --build     # rebuild + replace in one step
```

Day-to-day commands:

```bash
docker compose logs -f           # follow logs
docker compose restart           # restart the app
docker compose down              # stop and remove (data volume is kept)
docker compose down -v           # stop and also wipe cached data
```

Ollama note: inside a container, `localhost` refers to the container itself,
so the compose file already defaults `OLLAMA_HOST` to
`http://host.docker.internal:11434` (the machine running Docker). If Ollama
runs on a different server, set `OLLAMA_HOST` in `.env` to its real
`http://<ip>:11434`.

Prefer plain docker commands? The equivalent is:

```bash
docker build -t vittalens .
docker run -d --name vittalens -p 8030:8030 --restart unless-stopped \
  -v vittalens-data:/app/backend/data --env-file .env vittalens
```

(omit `--env-file .env` if you have no `.env` file)

## Manual setup (what the scripts do)

Requires Python 3.11+.

```bash
# 1. get the code onto the server and enter the project folder
cd investment_dashboard

# 2. create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Linux/macOS
#  .venv\Scripts\activate          # Windows (PowerShell/cmd)

# 3. install dependencies inside the venv
pip install -r backend/requirements.txt

# 4. configure (optional — the app runs with zero config)
cp .env.example .env               # Windows: copy .env.example .env

# 5. start the server — serves the API and the frontend together
uvicorn backend.main:app --host 0.0.0.0 --port 8030
```

Notes for hosting:

- `--host 0.0.0.0` makes the app reachable from other machines; open port
  8030 in the server's firewall/security group.
- Use `--reload` only during development (auto-restarts on code changes).
- To change the port, just change `--port` — the frontend calls the API with
  relative URLs, so no code changes are needed.
- To keep it running after you log out, run it under `nohup`, `tmux`, or a
  systemd service, e.g.:
  `nohup .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8030 &`

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
