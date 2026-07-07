"""Generate dummy model outputs for Page 2 (Model Analytics).

Run directly (python -m backend.data.dummy.generate) to regenerate
model_outputs.json. The numbers are deterministic (seeded) so the demo is
stable. Replace the loader in backend/routers/models.py with real model
functions when the DS pipeline is ready — the JSON schema here is the contract.
"""
import datetime as dt
import json
import math
import random
from pathlib import Path

OUT = Path(__file__).parent / "model_outputs.json"

INDEX_PARAMS = {  # id: (start_value, annual_drift, volatility)
    "nifty50": (12000, 0.13, 0.030),
    "niftybank": (26000, 0.12, 0.045),
    "niftyit": (24000, 0.15, 0.055),
    "cpse": (28, 0.18, 0.060),
    "bharat22": (48, 0.14, 0.040),
}
HISTORY_MONTHS = 60
FORECAST_MONTHS = 12


def month_list(n_back: int, n_fwd: int) -> list[str]:
    today = dt.date.today().replace(day=1)
    months = []
    for i in range(-n_back + 1, n_fwd + 1):
        y, m = divmod(today.month - 1 + i, 12)
        months.append(f"{today.year + y}-{m + 1:02d}")
    return months


def generate() -> dict:
    rng = random.Random(42)
    hist_months = month_list(HISTORY_MONTHS, 0)
    # month_list(0, n) already starts at next month, so no slicing needed
    fwd_months = month_list(0, FORECAST_MONTHS)

    growth, deltas = {}, {}
    for idx, (start, drift, vol) in INDEX_PARAMS.items():
        value, values = start, []
        for _ in hist_months:
            value *= math.exp(rng.gauss(drift / 12, vol))
            values.append(round(value, 2))
        growth_rate = [None] * 12 + [
            round((values[i] / values[i - 12] - 1) * 100, 2) for i in range(12, len(values))
        ]
        monthly_delta = [None] + [
            round((values[i] / values[i - 1] - 1) * 100, 2) for i in range(1, len(values))
        ]
        growth[idx] = {"values": values, "growth_rate_yoy": growth_rate}
        deltas[idx] = monthly_delta

    # model-predicted monthly allocation % (softmax over noisy momentum scores)
    allocations = []
    for m in fwd_months:
        scores = {idx: rng.uniform(0.5, 2.2) for idx in INDEX_PARAMS}
        total = sum(math.exp(s) for s in scores.values())
        alloc = {idx: round(math.exp(s) / total * 100, 1) for idx, s in scores.items()}
        drift_fix = round(100 - sum(alloc.values()), 1)  # rounding residue → largest slot
        alloc[max(alloc, key=alloc.get)] = round(alloc[max(alloc, key=alloc.get)] + drift_fix, 1)
        allocations.append({"month": m, **alloc})

    comparison = {}
    for idx, (start, drift, vol) in INDEX_PARAMS.items():
        vals = growth[idx]["values"]
        comparison[idx] = {
            "pe": round(rng.uniform(10, 30), 1),
            "pb": round(rng.uniform(1.8, 7.5), 1),
            "ma_50d": round(sum(vals[-2:]) / 2, 2),
            "ma_200d": round(sum(vals[-7:]) / 7, 2),
            "cagr_1y": round((vals[-1] / vals[-13] - 1) * 100, 2),
            "cagr_5y": round(((vals[-1] / vals[0]) ** (1 / 5) - 1) * 100, 2),
            "projected_cagr": round(drift * 100 + rng.uniform(-2, 2), 2),
        }

    best = max(comparison, key=lambda i: comparison[i]["projected_cagr"])
    current_alloc = allocations[0]
    top_alloc_idx = max(INDEX_PARAMS, key=lambda i: current_alloc[i])
    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "months": hist_months,
        "forecast_months": fwd_months,
        "growth": growth,
        "deltas": deltas,
        "comparison": comparison,
        "allocations": allocations,
        "summary": {
            "projected_portfolio_cagr": round(
                sum(comparison[i]["projected_cagr"] * current_alloc[i] for i in INDEX_PARAMS) / 100, 2),
            "best_index": best,
            "best_index_cagr": comparison[best]["projected_cagr"],
            "top_allocation_index": top_alloc_idx,
            "top_allocation_pct": current_alloc[top_alloc_idx],
            "current_month": current_alloc["month"],
        },
    }


def ensure() -> dict:
    """Load model outputs, generating the file on first run."""
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    data = generate()
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return data


if __name__ == "__main__":
    OUT.write_text(json.dumps(generate(), indent=1), encoding="utf-8")
    print(f"wrote {OUT}")
