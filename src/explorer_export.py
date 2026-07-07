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
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
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
        calendar = con.execute(
            """
            SELECT ba_code,
                   CAST(EXTRACT(month FROM ts_utc - INTERVAL 7 HOUR) AS INT) AS month,
                   CAST(EXTRACT(hour  FROM ts_utc - INTERVAL 7 HOUR) AS INT) AS hour,
                   ROUND(100.0 * AVG(CASE WHEN lmp_usd_mwh <= 0 THEN 1 ELSE 0 END), 1)
                       AS neg_pct
            FROM eim_prices GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
            """
        ).df()
        neg_annual = con.execute(
            """
            SELECT ba_code, CAST(EXTRACT(year FROM ts_utc - INTERVAL 7 HOUR) AS INT) AS year,
                   SUM(CASE WHEN lmp_usd_mwh <= 0 THEN 1 ELSE 0 END) AS neg_hours
            FROM eim_prices GROUP BY 1, 2 ORDER BY 1, 2
            """
        ).df()
        value = None
        if "value_annual" in tables:
            value = con.execute(
                """
                SELECT CAST(year AS INT) AS year,
                       ROUND(SUM(curt_lo_mwh))            AS lo_mwh,
                       ROUND(SUM(curt_mid_mwh))           AS mid_mwh,
                       ROUND(SUM(curt_hi_mwh))            AS hi_mwh,
                       ROUND(SUM(avoided_cost_mid_usd))   AS avoided_usd_mid,
                       ROUND(SUM(avoided_cost_hi_usd))    AS avoided_usd_hi,
                       ROUND(SUM(homes_mid))              AS homes_mid,
                       ROUND(SUM(homes_hi))               AS homes_hi,
                       ROUND(SUM(tco2_mid))               AS tco2_mid
                FROM value_annual GROUP BY 1 ORDER BY 1
                """
            ).df()

    payload = {
        "mode": pipeline_mode(),
        "years": sorted(monthly["year"].astype(int).unique().tolist()),
        "monthly_surplus": monthly.astype(
            {"year": int, "month": int, "lo_mwh": int, "mid_mwh": int, "hi_mwh": int}
        ).to_dict(orient="records"),
        "scenarios": scenarios.to_dict(orient="records"),
        "neg_calendar": calendar.to_dict(orient="records"),
        "neg_annual": neg_annual.astype(
            {"year": int, "neg_hours": int}
        ).to_dict(orient="records"),
        "value_annual": value.to_dict(orient="records") if value is not None else [],
        "coverage_note": (
            "Surplus/value cover SRP + TEPC only (AZPS's reported solar cannot "
            "be attributed to its fleet — see the paper). Price calendar covers "
            "all three BAs, Apr 2023 onward."
        ),
    }
    out = EXPLORER_DIR / "data.js"
    out.write_text("window.C2C_DATA = " + json.dumps(payload) + ";\n")
    return out


if __name__ == "__main__":
    print(export())
