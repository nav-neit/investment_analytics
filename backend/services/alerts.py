"""Signals & Alerts: user-defined threshold rules evaluated on data refresh.

Rules and trigger history persist as JSON under backend/data. Supported
metrics map onto live overview fields and model allocations:
  pe / pb / div_yield / price / day_change_pct  → per-index live values
  allocation_shift                              → month-over-month model shift
Operators: "<", ">".
"""
import datetime as dt
import json
import uuid

from backend import config
from backend.data.dummy import generate as model_store
from backend.services import market_data

RULES_FILE = config.DATA_DIR / "alert_rules.json"
HISTORY_FILE = config.DATA_DIR / "alert_history.json"

METRICS = ["pe", "pb", "div_yield", "price", "day_change_pct", "allocation_shift"]


def _load(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return default


def _save(path, data):
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def list_rules() -> list[dict]:
    return _load(RULES_FILE, [])


def add_rule(index_id: str, metric: str, operator: str, threshold: float) -> dict:
    if index_id not in config.INDICES:
        raise ValueError(f"unknown index: {index_id}")
    if metric not in METRICS:
        raise ValueError(f"unknown metric: {metric}")
    if operator not in ("<", ">"):
        raise ValueError("operator must be '<' or '>'")
    rule = {
        "id": uuid.uuid4().hex[:8],
        "index": index_id,
        "metric": metric,
        "operator": operator,
        "threshold": float(threshold),
        "label": f"{config.INDICES[index_id]['name']} {metric} {operator} {threshold}",
        "created": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    rules = list_rules()
    rules.append(rule)
    _save(RULES_FILE, rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rules = list_rules()
    kept = [r for r in rules if r["id"] != rule_id]
    _save(RULES_FILE, kept)
    return len(kept) < len(rules)


def _current_values() -> dict[str, dict[str, float]]:
    values = {o["id"]: {k: o[k] for k in ("pe", "pb", "div_yield", "price", "day_change_pct")
                        if o.get(k) is not None}
              for o in market_data.get_indices_overview()}
    # allocation_shift: |this month − last generated month| from the model
    model = model_store.ensure()
    allocs = model["allocations"]
    if len(allocs) >= 2:
        for idx in config.INDICES:
            values[idx]["allocation_shift"] = round(abs(allocs[1][idx] - allocs[0][idx]), 1)
    return values


def evaluate() -> list[dict]:
    """Run every rule against current data; append new triggers to history.
    A rule fires at most once per calendar day to avoid alert spam."""
    values = _current_values()
    history = _load(HISTORY_FILE, [])
    today = dt.date.today().isoformat()
    fired_today = {(h["rule_id"], h["at"][:10]) for h in history}
    new = []
    for rule in list_rules():
        actual = values.get(rule["index"], {}).get(rule["metric"])
        if actual is None:
            continue
        hit = actual < rule["threshold"] if rule["operator"] == "<" else actual > rule["threshold"]
        if hit and (rule["id"], today) not in fired_today:
            new.append({
                "id": uuid.uuid4().hex[:8],
                "rule_id": rule["id"],
                "label": rule["label"],
                "actual": actual,
                "at": dt.datetime.now(dt.timezone.utc).isoformat(),
            })
    if new:
        history = (new + history)[:200]
        _save(HISTORY_FILE, history)
    return new


def get_history(limit: int = 50) -> list[dict]:
    return _load(HISTORY_FILE, [])[:limit]
