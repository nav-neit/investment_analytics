"""/api/companies — Level 3 company deep-dive endpoints."""
from fastapi import APIRouter, Query

from backend.services import llm_service, market_data, scraper

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/{symbol}")
def company_profile(symbol: str):
    return market_data.get_company_profile(symbol.upper())


@router.get("/{symbol}/history")
def company_history(symbol: str, range: str = Query("1Y", pattern="^(1M|6M|1Y|5Y|10Y|MAX)$")):
    return market_data.get_company_history(symbol.upper(), range)


@router.get("/{symbol}/news")
def company_news(symbol: str):
    symbol = symbol.upper()
    profile = market_data.get_company_profile(symbol)
    return {"symbol": symbol, "items": scraper.company_news(symbol, profile.get("name"))}


@router.get("/{symbol}/brief")
def company_brief(symbol: str):
    """LLM-synthesised investment brief (key developments, sentiment, risks, outlook)."""
    symbol = symbol.upper()
    profile = market_data.get_company_profile(symbol)
    news = scraper.company_news(symbol, profile.get("name"))
    return llm_service.investment_brief(symbol, profile, news)
