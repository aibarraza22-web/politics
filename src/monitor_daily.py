"""Daily monitor: yesterday's negative-price hours at Arizona's EIM nodes.

Runs from GitHub Actions on a daily cron (no API key — OASIS is public),
appends one record per BA-day to explorer/monitor.js (a JS global, rolling
window), which the explorer renders as a "yesterday on the grid" strip.
This is what turns a static paper into a monitor that is current every
morning.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from src.estimators.b_eim_prices import EIM_NODES, _fetch_chunk_all_nodes, _node_cache

EXPLORER = Path(__file__).resolve().parent.parent / "explorer"
MONITOR = EXPLORER / "monitor.js"
KEEP_DAYS = 180


def load_existing() -> list[dict]:
    if not MONITOR.exists():
        return []
    text = MONITOR.read_text()
    return json.loads(text[text.index("=") + 1 :].rstrip().rstrip(";"))


def run(day: date | None = None) -> None:
    day = day or (date.today() - timedelta(days=2))  # OASIS publishes with lag
    start = pd.Timestamp(day)
    end = start + pd.Timedelta(days=1)
    _fetch_chunk_all_nodes(start, end)

    records = {(r["ba_code"], r["date"]): r for r in load_existing()}
    for ba, node in EIM_NODES.items():
        five = pd.read_parquet(_node_cache(node, start, end))
        hourly = five.set_index("ts5_utc")["lmp_usd_mwh"].resample("1h").mean().dropna()
        rec = {
            "ba_code": ba,
            "date": str(day),
            "neg_hours": int((hourly <= 0).sum()),
            "min_price": round(float(hourly.min()), 2),
            "mean_price": round(float(hourly.mean()), 2),
        }
        records[(ba, str(day))] = rec

    cutoff = str(day - timedelta(days=KEEP_DAYS))
    rows = sorted(
        (r for r in records.values() if r["date"] >= cutoff),
        key=lambda r: (r["date"], r["ba_code"]),
    )
    MONITOR.write_text("window.C2C_MONITOR = " + json.dumps(rows) + ";\n")
    print(f"monitor updated for {day}: "
          + ", ".join(f"{r['ba_code']}={r['neg_hours']}h" for r in rows
                      if r["date"] == str(day)))


if __name__ == "__main__":
    run()
