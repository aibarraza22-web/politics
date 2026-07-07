"""Export the explorer page's dataset (explorer/data.js).

The static explorer has no server and no CDN dependencies, so the data rides
along as a JS global. Everything exported is tagged with the pipeline mode;
the page shows a synthetic-data banner unless mode == "real".
"""

from __future__ import annotations

import json
from pathlib import Path

from src.pipeline import pipeline_mode
from src.store import connect

EXPLORER_DIR = Path(__file__).resolve().parent.parent / "explorer"


def export() -> Path:
    with connect(read_only=True) as con:
        monthly = con.execute(
            """
            SELECT EXTRACT(year  FROM ts_utc - INTERVAL 7 HOUR) AS year,
                   EXTRACT(month FROM ts_utc - INTERVAL 7 HOUR) AS month,
                   ROUND(SUM(COALESCE(curt_lo, 0)))  AS lo_mwh,
                   ROUND(SUM(COALESCE(curt_mid, 0))) AS mid_mwh,
                   ROUND(SUM(COALESCE(curt_hi, 0)))  AS hi_mwh
            FROM estimator_a_hourly GROUP BY 1, 2 ORDER BY 1, 2
            """
        ).df()
        scenarios = con.execute(
            """
            SELECT it_mw, flexibility, sla_frac, battery_h, band,
                   ROUND(100 * surplus_share, 1)   AS surplus_share_pct,
                   ROUND(100 * absorbed_frac, 1)   AS absorbed_pct,
                   ROUND(effective_cost_usd_mwh, 2) AS cost_usd_mwh
            FROM computeflex_scenarios WHERE band = 'mid'
            """
        ).df()

    payload = {
        "mode": pipeline_mode(),
        "years": sorted(monthly["year"].astype(int).unique().tolist()),
        "monthly_surplus": monthly.astype(
            {"year": int, "month": int, "lo_mwh": int, "mid_mwh": int, "hi_mwh": int}
        ).to_dict(orient="records"),
        "scenarios": scenarios.to_dict(orient="records"),
    }
    out = EXPLORER_DIR / "data.js"
    out.write_text("window.C2C_DATA = " + json.dumps(payload) + ";\n")
    return out


if __name__ == "__main__":
    print(export())
