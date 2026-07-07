"""QuantArtha — FastAPI entry point.

Run from the repo root:  uvicorn backend.main:app --reload
Serves the REST API under /api/* and the static frontend at /.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import FRONTEND_DIR
from backend.routers import alerts, chat, companies, indices, models, news

app = FastAPI(title="QuantArtha", version="1.0.0",
              description="Financial analytics & intelligence platform for Indian ETF indices.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # internal tool; tighten for external deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (indices.router, companies.router, models.router,
               news.router, chat.router, alerts.router):
    app.include_router(router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Static frontend last so /api/* wins the route match.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
