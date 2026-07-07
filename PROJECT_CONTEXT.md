# VittaLens — Full Project Context

> Purpose of this file: a single, self-contained briefing for an AI assistant
> (or a new developer) making changes to this project. It covers what the app
> is, the tech stack, folder structure, every API endpoint, end-to-end data
> flows, configuration, conventions, and common change recipes.

## 1. What the app is

**VittaLens** ("Vitta" = finance/wealth in Sanskrit + "Lens") is an internal
investment-team dashboard for tracking five Indian ETF indices:
**NIFTY 50, NIFTY Bank, NIFTY IT, CPSE, Bharat 22**.

Four capabilities:
1. **Index Screener** — 3-level drill-down: indices overview → index detail
   (constituents + charts) → company deep dive (fundamentals, news, AI brief).
2. **Model Analytics** — outputs of in-house data-science models (currently
   dummy data): growth curves, month deltas, index comparison, predicted
   monthly allocation %. Includes the **Signals & Alerts** module.
3. **Market News** — RSS aggregation → dedupe → LLM summaries → card grid,
   plus an LLM daily digest banner.
4. **AI Assistant** — chat with live platform context injected; slide-out
   panel on every page + full page at `assistant.html`.

Not investment advice; internal tool. Runs on **port 8030** (8000 is occupied
on the owner's machine — do not move it back).

## 2. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11+ / **FastAPI** + Uvicorn | all fetching/scraping/LLM/compute server-side |
| Frontend | **Pure HTML/CSS/vanilla JS** — no frameworks, no build step | served statically by FastAPI at `/` |
| Charts | **Chart.js 4** via CDN (`chart.umd.min.js`) | no date adapter; labels are plain strings |
| Market data | **yfinance** (Yahoo Finance) | disk-cached; synthetic fallback offline |
| News | RSS via **requests + feedparser**, HTML stripped with **BeautifulSoup** | ET, Mint, BBC, CNBC, Google News RSS |
| LLM | pluggable: **Anthropic API** or **Ollama** (local) or **none** | common interface in `llm_service.py` |
| Deployment | **Docker / docker-compose** (preferred) or venv + uvicorn | single container, port 8030 |

Python dependencies (`backend/requirements.txt`): fastapi, uvicorn[standard],
yfinance, requests, beautifulsoup4, feedparser, python-dotenv, pydantic,
anthropic (only used when `LLM_BACKEND=anthropic`).

Frontend external resources (CDN, loaded in HTML heads): Google Fonts
"Inter", Chart.js 4.4.7. Everything else is local.

## 3. Folder structure

```
investment_dashboard/
├── frontend/                  # static UI — FastAPI serves this at /
│   ├── index.html             # Page 1: Screener (all 3 levels, hash-routed)
│   ├── models.html            # Page 2: Model Analytics + Signals & Alerts
│   ├── news.html              # Page 3: Market News
│   ├── assistant.html         # Page 4: full-page AI assistant
│   ├── css/
│   │   ├── theme.css          # ALL design tokens (colors, radius, font) — edit theme here only
│   │   └── styles.css         # component styles (navbar, cards, tables, chat, bell…)
│   └── js/
│       ├── api.js             # fetch wrapper (API.get/post/del), fmt.* helpers,
│       │                      #   chartDefaults(), renderChart(), sparseTicks(),
│       │                      #   mdToHtml(), el(), showError(), sourceBadge(),
│       │                      #   cssVar(), navbar alerts-bell logic (runs on every page)
│       ├── screener.js        # Page 1 — hash router: #/ | #/index/<id> | #/company/<SYMBOL>
│       ├── models.js          # Page 2 — charts/tables loaders + alerts panel UI
│       ├── news.js            # Page 3 — digest banner, section tabs, card grid
│       └── chatbot.js         # assistant — panel or full-page, history, .md export
├── backend/
│   ├── main.py                # FastAPI app: CORS(*), routers, /api/health, static mount LAST
│   ├── config.py              # env config, TTLs, INDICES dict (names/yahoo symbols/colors/
│   │                          #   constituents/static P-E,P-B,div-yield), INDEX_ORDER
│   ├── requirements.txt
│   ├── routers/
│   │   ├── indices.py         # /api/indices…
│   │   ├── companies.py       # /api/companies…
│   │   ├── models.py          # /api/models… (loads dummy JSON — swap point for real models)
│   │   ├── news.py            # /api/news…
│   │   ├── chat.py            # /api/chat… (registers context providers at import)
│   │   └── alerts.py          # /api/alerts… (+ /api/alerts/digest weekly HTML)
│   ├── services/
│   │   ├── market_data.py     # yfinance fetch + cache + synthetic fallback; CAGR calc
│   │   ├── scraper.py         # fetch_feed(), company_news() via Google News RSS, strip_html()
│   │   ├── news_aggregator.py # SECTION_FEEDS, fetch→dedupe→summarise pipeline, daily digest
│   │   ├── llm_service.py     # backends (Anthropic/Ollama/None), summaries, briefs,
│   │   │                      #   chat sessions (in-memory), register_context_provider()
│   │   └── alerts.py          # rule CRUD (JSON files), evaluate(), history
│   ├── data/
│   │   ├── dummy/generate.py  # dummy model-output generator (seeded, deterministic)
│   │   ├── dummy/model_outputs.json   # generated; schema = contract for /api/models
│   │   ├── cache/             # runtime disk cache (gitignore-able, safe to delete)
│   │   ├── alert_rules.json   # runtime, created on first rule
│   │   └── alert_history.json # runtime, created on first trigger
│   └── utils/cache.py         # file-backed TTL cache: get_or_fetch(key, ttl, fn),
│                              #   serves STALE data if the fetch fn raises
├── Dockerfile                 # python:3.12-slim, non-root user, healthcheck, port 8030
├── docker-compose.yml         # preferred deploy: build + port + volume + ${VAR:-default} env
├── .dockerignore              # excludes .venv/.git/cache/.env from image
├── .env.example               # template for .env (LLM backend, TTLs)
├── start_server.sh / .bat     # venv bootstrap + uvicorn on 8030 (non-Docker path)
└── README.md                  # user-facing setup/deploy instructions
```

## 4. REST API map (all JSON unless noted)

| Endpoint | Returns |
|---|---|
| `GET /api/health` | `{status:"ok"}` |
| `GET /api/indices` | overview list: price, day %, 52w H/L, P/E, P/B, div yield, CAGR 1/5/10y, 60d sparkline, `source` |
| `GET /api/indices/{id}` | same for one index (ids: `nifty50, niftybank, niftyit, cpse, bharat22`) |
| `GET /api/indices/{id}/history?range=1M\|6M\|1Y\|5Y\|10Y\|MAX` | dates, close, volume, pe (price-proxy series), color |
| `GET /api/indices/{id}/constituents` | per-company quotes: price, day %, mcap ₹Cr, P/E, P/B, div %, ROE, 52w |
| `GET /api/companies/{symbol}` | profile: sector, summary, metrics (EPS, margins, D/E, beta…), quote, parent index |
| `GET /api/companies/{symbol}/history?range=` | price + volume series |
| `GET /api/companies/{symbol}/news` | scraped headlines (Google News RSS) |
| `GET /api/companies/{symbol}/brief` | LLM investment brief (markdown), cached 6h |
| `GET /api/models/summary` | stat-card data: projected CAGR, best index, top allocation |
| `GET /api/models/growth?start=YYYY-MM&end=` | 60 months of index values + YoY growth-rate per index |
| `GET /api/models/deltas?start=&end=` | month-over-month Δ% per index |
| `GET /api/models/comparison` | P/E, P/B, MA50/200, CAGR 1y/5y, projected CAGR per index |
| `GET /api/models/allocations?start=&end=` | 12 forecast months of allocation % rows |
| `GET /api/models/{dataset}/csv` | CSV download (growth/deltas/comparison/allocations) |
| `GET /api/news?section=&refresh=true` | summarised cards; sections: markets, economy, banking, global, commodities, policy |
| `GET /api/news/digest?refresh=true` | one-paragraph LLM daily digest |
| `POST /api/chat` body `{session_id, message}` | `{reply, backend, turns}` |
| `GET/DELETE /api/chat/history/{session_id}` | conversation history / clear |
| `GET /api/chat/status` | `{backend, available}` |
| `GET /api/alerts/rules` | `{rules, indices, metrics}` (metrics list feeds the UI form) |
| `POST /api/alerts/rules` body `{index, metric, operator("<"/">"), threshold}` | created rule |
| `DELETE /api/alerts/rules/{id}` | remove rule |
| `POST /api/alerts/evaluate` | runs all rules now → `{fired:[…]}` (max 1 fire/rule/day) |
| `GET /api/alerts/history` | trigger log (newest first) |
| `GET /api/alerts/digest` | standalone HTML weekly digest (model summary + top news) |

## 5. End-to-end flows

**Screener (Page 1)** — `screener.js` routes on `location.hash`:
`#/` overview table → click row → `#/index/<id>` (stat tiles, price & P/E
charts with range toggle, sortable/filterable constituents table) → click
company → `#/company/<SYMBOL>` (fundamentals tiles, price+volume charts,
scraped news list, AI brief). Data path: router → `market_data.py` →
`utils/cache.py` (disk, TTL) → yfinance. If yfinance fails/offline, a
deterministic **synthetic** random-walk series is returned and the UI shows a
red "demo data" badge (`source` field: `live` vs `synthetic`). Index-level
P/E, P/B, dividend yield and market cap are **static reference values** in
`config.py` (NSE publishes them; Yahoo doesn't) — the index P/E *trend* chart
is a price-proxy placeholder.

**Model Analytics (Page 2)** — `models.js` calls `/api/models/*`; router
loads `backend/data/dummy/model_outputs.json` (auto-generated on first run by
`generate.py`, regenerate with `python -m backend.data.dummy.generate`).
The JSON schema is the contract: keys `months`, `growth`, `deltas`,
`comparison`, `allocations`, `summary`. **To plug in real models, replace
`_load()` in `backend/routers/models.py`** — endpoints and frontend stay
unchanged. Month-range filter is applied server-side via `start`/`end` query
params (format `YYYY-MM`).

**News (Page 3)** — `news_aggregator.py`: fetch all feeds in `SECTION_FEEDS`
(parallel) → strip HTML → dedupe by normalised title → per-item LLM summary
(`summarize_news_item`) → cache 30 min. Digest: top 25 headlines → one LLM
paragraph. `?refresh=true` busts the cache (the ↻ button).

**Assistant** — `chatbot.js` keeps a session id in
`localStorage["vittalens_chat_session"]`. `POST /api/chat` →
`llm_service.chat()`: gathers context from **registered providers**
(currently: live index snapshot from `market_data.market_snapshot_text()` and
recent headlines from `news_aggregator.recent_headlines_text()`, both
registered in `routers/chat.py`), prepends it to the system prompt, calls the
selected backend, stores history **in memory** (lost on server restart;
30-turn cap). Export button downloads the conversation as `.md`. To add a
knowledge-repo source later: `llm_service.register_context_provider(fn)`
where `fn(user_message) -> str`.

**LLM selection** — `config.LLM_BACKEND`: `anthropic` | `ollama` | `none`.
`get_backend(deep=bool)` returns the backend; Ollama uses
`OLLAMA_FAST_MODEL` for news cards/digests and `OLLAMA_DEEP_MODEL` for chat
and briefs. `none` (default) degrades every LLM feature to extractive text
with a setup hint — the app must always work with zero config.

**Alerts** — rules persist in `backend/data/alert_rules.json`. Metrics:
`pe, pb, div_yield, price, day_change_pct` (from live index overview) and
`allocation_shift` (|month₂ − month₁| from model allocations). `evaluate()`
runs on every page load (api.js bell logic calls `POST /api/alerts/evaluate`)
and dedupes to one fire per rule per calendar day; history capped at 200.
Bell dropdown in navbar shows history on all pages.

**Caching** — `utils/cache.py`: JSON files under `backend/data/cache`, key →
`{expires, value}`. `get_or_fetch` serves **stale data if the fetch raises**
(stale beats a 500). TTLs in `config.py` (env-overridable): quotes 10 min,
history 1 h, fundamentals 6 h, news 30 min, LLM outputs 6 h. Delete the
cache folder anytime to reset.

## 6. Frontend conventions

- **Theme = light** (owner's explicit preference — do NOT ship dark-first):
  page `#F2F6FB`, cards `#FFFFFF`, ink navy `#16233A`, accent `#1E3A8A`.
  ALL colors live as CSS custom properties in `frontend/css/theme.css`;
  JS reads them via `cssVar("--token")` — never hardcode hex in JS/HTML.
- **Series colors** (one per index, fixed, CVD-validated on white):
  NIFTY 50 `#2A78D6` blue · NIFTY Bank `#0E9866` teal · NIFTY IT `#4A3AA7`
  violet · CPSE `#B8860B` gold · Bharat 22 `#C23D6F` magenta. These are ALSO
  defined in `backend/config.py` (served in API payloads) — keep both in sync.
  `--gain #059669` / `--loss #DC2626` are status colors, never series colors.
- Every chart has a matching **table** and a legend for multi-series; escape
  all dynamic text with `fmt.esc()` (XSS); numbers via `fmt.num/price/cr/pct`
  (Indian formatting, ₹ L Cr for market cap).
- Loading states: `.skeleton` blocks or `.spinner`; failures render via
  `showError(el, err, msg)` — never a blank area.
- No build step: keep everything browser-native ES (no imports/modules).

## 7. Configuration (.env — all optional)

```
LLM_BACKEND=none|anthropic|ollama     # default none
ANTHROPIC_API_KEY=                    # for anthropic
ANTHROPIC_MODEL=claude-haiku-4-5-20251001
OLLAMA_HOST=http://localhost:11434    # in Docker: http://host.docker.internal:11434
OLLAMA_FAST_MODEL=llama3.2:3b
OLLAMA_DEEP_MODEL=llama3.2:3b         # e.g. a finance-tuned 8B
TTL_QUOTES / TTL_HISTORY / TTL_FUNDAMENTALS / TTL_NEWS / TTL_LLM  # seconds
```

## 8. Run / deploy

- **Docker (preferred):** `docker compose up -d --build` → port 8030, named
  volume `vittalens-data` persists `backend/data`. Env defaults are inlined
  in docker-compose.yml as `${VAR:-default}` so no `.env` is required.
- **venv:** `./start_server.sh` (Linux) / `start_server.bat` (Windows), or
  manually: venv → `pip install -r backend/requirements.txt` →
  `uvicorn backend.main:app --host 0.0.0.0 --port 8030`.
- API docs auto-generated at `/docs`. Health: `/api/health`.
- The app needs outbound internet for live data; without it everything still
  renders from synthetic/fallback data.

## 9. Common change recipes

- **Add/replace an index:** edit `INDICES` + `INDEX_ORDER` in
  `backend/config.py` (yahoo symbol, constituents, static valuations, a NEW
  validated series color) and add a matching `--series-<id>` token in
  `theme.css`. Everything else adapts.
- **Swap dummy models for real ones:** replace `_load()` in
  `backend/routers/models.py`; keep the JSON schema from
  `backend/data/dummy/model_outputs.json`.
- **Add a news source/section:** add the RSS URL to `SECTION_FEEDS` (and
  `SECTION_LABELS`) in `backend/services/news_aggregator.py`.
- **Add an alert metric:** extend `METRICS` + `_current_values()` in
  `backend/services/alerts.py`; the UI form picks it up automatically.
- **Add an LLM provider:** new class with `complete(system, messages,
  max_tokens) -> str` in `llm_service.py`, wire it in `get_backend()`.
- **Switch to official NSE data:** reimplement the `_fetch_*` functions in
  `backend/services/market_data.py`; keep signatures and payload shapes.

## 10. Known placeholders / gotchas

- Index-level P/E / P/B / div-yield / market-cap are static config values;
  the index P/E trend chart is a price-proxy. Swap in an NSE source later.
- Model Analytics data is dummy (seeded random) — clearly labelled in the UI.
- Chat history is in-memory only; restart clears it (exports are client-side).
- yfinance is unofficial — quotes are cached and can be ~10 min stale by design.
- Port is 8030 everywhere (launch config, scripts, Dockerfile, compose, README).
- Windows dev box: prefer editing files with UTF-8-safe tools (PowerShell
  `Get-Content`/`Set-Content` roundtrips have mangled Unicode before).
