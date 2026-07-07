"""/api/news — aggregated, deduplicated, LLM-summarised market news."""
from fastapi import APIRouter, Query

from backend.services import news_aggregator

router = APIRouter(prefix="/api/news", tags=["news"])


@router.get("")
def news(section: str | None = Query(None), refresh: bool = Query(False)):
    return news_aggregator.get_news(section, force=refresh)


@router.get("/digest")
def digest(refresh: bool = Query(False)):
    return news_aggregator.get_digest(force=refresh)
