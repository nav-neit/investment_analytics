"""/api/indices — Level 1 overview and Level 2 index detail endpoints."""
from fastapi import APIRouter, HTTPException, Query

from backend import config
from backend.services import market_data

router = APIRouter(prefix="/api/indices", tags=["indices"])


def _require(index_id: str) -> dict:
    idx = config.INDICES.get(index_id)
    if not idx:
        raise HTTPException(404, f"unknown index: {index_id}")
    return idx


@router.get("")
def list_indices():
    return {"indices": market_data.get_indices_overview()}


@router.get("/{index_id}")
def index_detail(index_id: str):
    _require(index_id)
    overview = next(o for o in market_data.get_indices_overview() if o["id"] == index_id)
    return overview


@router.get("/{index_id}/history")
def index_history(index_id: str, range: str = Query("1Y", pattern="^(1M|6M|1Y|5Y|10Y|MAX)$")):
    idx = _require(index_id)
    hist = market_data.get_history(idx["yahoo"], range)
    # P/E trend derived from price vs. current published P/E — a placeholder
    # proxy until an NSE valuation-history source is wired in.
    closes = hist["close"]
    pe_now = idx["static"]["pe"]
    pe_series = [round(pe_now * c / closes[-1], 2) for c in closes] if closes else []
    return {**hist, "pe": pe_series, "name": idx["name"], "color": idx["color"]}


@router.get("/{index_id}/constituents")
def index_constituents(index_id: str):
    _require(index_id)
    return {"index": index_id, "companies": market_data.get_constituents(index_id)}
