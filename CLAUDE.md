# VittaLens

Read `PROJECT_CONTEXT.md` at the repo root before making changes — it is the
complete project briefing (stack, structure, API map, data flows, conventions,
change recipes) and is kept authoritative.

Hard rules:
- App name is **VittaLens** (never QuantArtha). Port is **8030**.
- UI theme is **light** (white / very light blue + navy) — owner preference;
  all colors come from tokens in `frontend/css/theme.css`, no hardcoded hex.
- Frontend stays vanilla HTML/CSS/JS (no frameworks, no build step);
  backend stays Python/FastAPI; frontend talks to backend only via `/api/*`
  with relative URLs.
- Every external fetch goes through `backend/utils/cache.py` and must degrade
  gracefully (synthetic/fallback data, never a blank page).
- After changing anything user-visible, update `PROJECT_CONTEXT.md` if the
  structure, endpoints, or conventions changed.
