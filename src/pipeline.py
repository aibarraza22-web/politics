"""Pipeline orchestration: demo mode vs real mode.

Demo mode (default in this repo until live data access is verified) generates
synthetic fixtures with injected ground-truth curtailment and runs the exact
same downstream code as real mode. Real mode pulls EIA data (requires
EIA_API_KEY and network access) into the same table schemas.

Every duckdb table row carries its provenance via the `pipeline_meta` table
(mode + generation timestamp); figures surface the mode as a banner.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import pandas as pd

from src.store import connect, read_table, write_table

TOLERANCE_930_VS_923 = 0.10  # documented reconciliation tolerance (fraction)


def build_demo(seed: int = 42) -> None:
    from src import demo_data

    demo_data.persist(demo_data.generate(seed=seed))
    write_table(
        pd.DataFrame(
            [{"mode": "demo", "built_at_utc": datetime.now(timezone.utc).isoformat()}]
        ),
        "pipeline_meta",
    )


SUSPECT_FACTOR = 1.25  # 930 solar above this x fleet AC nameplate is impossible


def build_real(start: str = "2022-01-01", end: str = "2024-12-31", fleet_year: int = 2024) -> None:
    """Live-data build. VERIFIED-LIVE fetchers only (see SOURCES.md).

    Fleet is restricted to the three AZ BAs (live EIA-860 shows ~1.8 GW of
    AZ solar interconnected to CISO/WALC, outside our 930 series). Hours
    with physically impossible 930 solar (> SUSPECT_FACTOR x fleet AC, e.g.
    AZPS 2024-01-25 at 3,822 MW vs a 919 MW fleet) are folded into the
    unusable-hour flag alongside EIA's imputed hours.
    """
    from src.estimators.b_eim_prices import fetch_eim_prices
    from src.fleet.eia860 import build_az_solar_fleet, generator_capacities
    from src.fleet.eia923 import fetch_monthly_plant_gen
    from src.fleet.eia930 import BA_CODES, fetch_hourly_solar_bulk
    from src.potential.weather import fetch_fleet_weather

    years = tuple(range(int(start[:4]), int(end[:4]) + 1))

    fleet = build_az_solar_fleet(fleet_year)
    fleet = fleet[fleet["ba_code"].isin(BA_CODES)].reset_index(drop=True)
    write_table(fleet, "fleet")
    gens = generator_capacities(fleet_year)
    write_table(gens[gens["plant_id"].isin(fleet["plant_id"])], "fleet_generators")

    hourly = fetch_hourly_solar_bulk(years=years)
    fleet_ac = fleet.groupby("ba_code")["capacity_mw_ac"].sum()
    cap = hourly["ba_code"].map(fleet_ac)
    suspect = hourly["solar_mw"] > SUSPECT_FACTOR * cap
    hourly["is_imputed"] = hourly["is_imputed"].astype(bool) | suspect
    write_table(hourly, "hourly_ba_solar")
    print(f"unusable hours: imputed+suspect={int(hourly['is_imputed'].sum())} "
          f"(suspect alone: {int(suspect.sum())})")

    write_table(fetch_monthly_plant_gen(start[:7], end[:7]), "monthly_plant_gen")
    write_table(fetch_fleet_weather(fleet, start, end), "weather_obs")
    write_table(fetch_eim_prices(), "eim_prices")
    write_table(
        pd.DataFrame(
            [{"mode": "real", "built_at_utc": datetime.now(timezone.utc).isoformat()}]
        ),
        "pipeline_meta",
    )


def pipeline_mode() -> str:
    try:
        return read_table("pipeline_meta")["mode"].iat[0]
    except Exception:
        return "unbuilt"


def reconciled_ba_codes() -> list[str]:
    """BAs whose 930 solar is attributable to the modeled fleet (every year
    within tolerance). Estimator A is only defensible for these.

    Real-data finding (2026-07-07): AZPS fails — its 930 solar exceeds the
    sum of ALL attributable utility-scale plant generation by 40-74%
    (growing yearly), unexplained by CISO/WALC plant reattribution (NNLS
    over monthly profiles yields nonphysical weights). Pattern is consistent
    with AZPS reporting estimated distributed/small-scale solar in 930.
    SRP and TEPC reconcile within 3-8%.
    """
    rec = read_table("reconciliation")
    ok = rec.groupby("ba_code")["within_tolerance"].all()
    return sorted(ok[ok].index)


def reconcile_930_vs_plant_sums() -> pd.DataFrame:
    """Fleet-vs-930 acceptance check (Phase 1).

    Compares annual BA solar energy from the hourly 930-like series
    (imputed hours excluded) against the sum of monthly per-plant generation
    (923-like) for the same BA-year. Passes when relative gap is within
    TOLERANCE_930_VS_923. Result persisted as `reconciliation`.
    """
    with connect(read_only=True) as con:
        hourly = con.execute(
            """
            SELECT h.ba_code,
                   EXTRACT(year FROM h.ts_utc - INTERVAL 7 HOUR) AS year,
                   SUM(CASE WHEN NOT COALESCE(h.is_imputed, TRUE) THEN h.solar_mw ELSE 0 END)
                       AS mwh_930,
                   SUM(CASE WHEN COALESCE(h.is_imputed, TRUE) THEN 1 ELSE 0 END) AS unusable_hours
            FROM hourly_ba_solar h
            GROUP BY 1, 2
            """
        ).df()
        plant = con.execute(
            """
            SELECT f.ba_code, m.year, SUM(m.net_gen_mwh) AS mwh_923
            FROM monthly_plant_gen m JOIN fleet f USING (plant_id)
            GROUP BY 1, 2
            """
        ).df()
    rec = hourly.merge(plant, on=["ba_code", "year"], how="inner")
    # 923 covers all hours; the imputed-excluded 930 sum covers slightly fewer.
    # Scale 923 by usable-hour coverage before comparing.
    hours_in_year = rec["year"].map(lambda y: 8784 if y % 4 == 0 else 8760)
    coverage = 1 - rec["unusable_hours"] / hours_in_year
    rec["mwh_923_scaled"] = rec["mwh_923"] * coverage
    rec["rel_gap"] = (rec["mwh_930"] - rec["mwh_923_scaled"]) / rec["mwh_923_scaled"]
    rec["within_tolerance"] = rec["rel_gap"].abs() <= TOLERANCE_930_VS_923
    write_table(rec, "reconciliation")
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["demo", "real"], default="demo")
    args = ap.parse_args()
    if args.mode == "demo":
        build_demo()
    else:
        build_real()
    rec = reconcile_930_vs_plant_sums()
    print(rec.to_string(index=False))
    if not rec["within_tolerance"].all():
        raise SystemExit("reconciliation outside documented tolerance — inspect before proceeding")


if __name__ == "__main__":
    main()
