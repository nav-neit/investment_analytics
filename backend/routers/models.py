"""/api/models — data-science model outputs (dummy data for now).

The dummy JSON in backend/data/dummy is the schema contract. To go live,
replace `_load()` with calls into the real model pipeline — every endpoint
below (and therefore the frontend) stays unchanged.
"""
import csv
import io

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend import config
from backend.data.dummy import generate as model_store

router = APIRouter(prefix="/api/models", tags=["models"])


def _load() -> dict:
    return model_store.ensure()


def _month_filter(months: list[str], start: str | None, end: str | None) -> list[int]:
    return [i for i, m in enumerate(months)
            if (not start or m >= start) and (not end or m <= end)]


@router.get("/summary")
def summary():
    data = _load()
    s = dict(data["summary"])
    s["best_index_name"] = config.INDICES[s["best_index"]]["name"]
    s["top_allocation_name"] = config.INDICES[s["top_allocation_index"]]["name"]
    s["generated_at"] = data["generated_at"]
    return s


@router.get("/growth")
def growth(start: str | None = Query(None), end: str | None = Query(None)):
    """Long-term index values + YoY growth-rate series per index."""
    data = _load()
    keep = _month_filter(data["months"], start, end)
    return {
        "months": [data["months"][i] for i in keep],
        "series": {
            idx: {
                "name": config.INDICES[idx]["name"],
                "color": config.INDICES[idx]["color"],
                "values": [g["values"][i] for i in keep],
                "growth_rate_yoy": [g["growth_rate_yoy"][i] for i in keep],
            }
            for idx, g in data["growth"].items()
        },
    }


@router.get("/deltas")
def deltas(start: str | None = None, end: str | None = None):
    """Combined month-over-month delta (%) across all 5 indices."""
    data = _load()
    keep = _month_filter(data["months"], start, end)
    return {
        "months": [data["months"][i] for i in keep],
        "series": {
            idx: {
                "name": config.INDICES[idx]["name"],
                "color": config.INDICES[idx]["color"],
                "delta_pct": [d[i] for i in keep],
            }
            for idx, d in data["deltas"].items()
        },
    }


@router.get("/comparison")
def comparison():
    """P/E, P/B, moving averages and CAGR side-by-side across indices."""
    data = _load()
    return {
        "indices": [
            {"id": idx, "name": config.INDICES[idx]["name"],
             "color": config.INDICES[idx]["color"], **metrics}
            for idx, metrics in data["comparison"].items()
        ]
    }


@router.get("/allocations")
def allocations(start: str | None = None, end: str | None = None):
    """Model-predicted monthly allocation split (%) across indices."""
    data = _load()
    rows = [a for a in data["allocations"]
            if (not start or a["month"] >= start) and (not end or a["month"] <= end)]
    return {
        "months": [a["month"] for a in rows],
        "indices": [{"id": i, "name": config.INDICES[i]["name"],
                     "color": config.INDICES[i]["color"]} for i in config.INDEX_ORDER],
        "rows": rows,
    }


@router.get("/{dataset}/csv")
def download_csv(dataset: str):
    """Download any model table as CSV (growth | deltas | allocations | comparison)."""
    data = _load()
    buf = io.StringIO()
    w = csv.writer(buf)
    names = {i: config.INDICES[i]["name"] for i in config.INDEX_ORDER}
    if dataset == "allocations":
        w.writerow(["Month"] + [names[i] + " %" for i in config.INDEX_ORDER])
        for a in data["allocations"]:
            w.writerow([a["month"]] + [a[i] for i in config.INDEX_ORDER])
    elif dataset == "growth":
        w.writerow(["Month"] + [names[i] for i in config.INDEX_ORDER])
        for k, m in enumerate(data["months"]):
            w.writerow([m] + [data["growth"][i]["values"][k] for i in config.INDEX_ORDER])
    elif dataset == "deltas":
        w.writerow(["Month"] + [names[i] + " Δ%" for i in config.INDEX_ORDER])
        for k, m in enumerate(data["months"]):
            w.writerow([m] + [data["deltas"][i][k] for i in config.INDEX_ORDER])
    elif dataset == "comparison":
        cols = ["pe", "pb", "ma_50d", "ma_200d", "cagr_1y", "cagr_5y", "projected_cagr"]
        w.writerow(["Index"] + cols)
        for i in config.INDEX_ORDER:
            w.writerow([names[i]] + [data["comparison"][i][c] for c in cols])
    else:
        raise HTTPException(404, "unknown dataset")
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=quantartha_{dataset}.csv"})
