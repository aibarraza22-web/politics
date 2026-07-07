"""Estimator A — potential-vs-actual gap with propagated uncertainty.

Counterfactual: on an unconstrained hour, actual = potential_cal * (1 - r),
where r is the relative residual whose distribution was measured on
unconstrained hours (src/potential/calibrate.py). Curtailment estimate at
residual quantile q:

    curt_q = potential_cal * (1 - r_q) - actual        (clipped at 0)

The band (q=0.05 .. 0.95) therefore carries weather-model error, unobserved
outages, and derates — the confounders — into every reported number. Hours
flagged imputed are excluded and annual totals are scaled by usable-hour
coverage (never silently ingested).

Zero-clipping bias correction: clipping hourly gaps at zero turns symmetric
model noise into a positive sum — on hours with zero true curtailment the
clipped gap still averages > 0. The demo harness (known injected truth)
exposed this directly. We therefore measure the same clipped statistic on
presumed-unconstrained hours (where true curtailment ~ 0) and subtract that
per-daylight-hour baseline from every annual total, per band. The correction
is reported in the output table (`baseline_*_mwh`), not hidden.

What this estimator sees: the UNION of economic and physical curtailment
plus anything else that suppresses output below modeled potential. It cannot
split economic from physical on its own — that distinction comes from
Estimator B coincidence and is reported as such.
"""

from __future__ import annotations

import pandas as pd

from src.store import connect, write_table

DAYLIGHT_FRAC_OF_PEAK = 0.05  # hour counts as daylight if potential > 5% of BA peak


def run() -> pd.DataFrame:
    with connect(read_only=True) as con:
        df = con.execute("SELECT * FROM potential_ba_hour").df()
        quants = con.execute("SELECT * FROM residual_quantiles").df()

    q = quants.pivot(index="ba_code", columns="quantile", values="rel_residual")
    df = df.merge(q, left_on="ba_code", right_index=True)

    usable = ~df["is_imputed"].fillna(True).astype(bool)
    peak = df.groupby("ba_code")["potential_mw_cal"].transform("max")
    daylight = df["potential_mw_cal"] > DAYLIGHT_FRAC_OF_PEAK * peak
    live = usable & daylight

    for name, rq in [("curt_mid", 0.5), ("curt_lo", 0.95), ("curt_hi", 0.05)]:
        est = df["potential_mw_cal"] * (1 - df[rq]) - df["solar_mw"]
        df[name] = est.clip(lower=0).where(live, other=pd.NA)

    hourly = df[["ba_code", "ts_utc", "curt_lo", "curt_mid", "curt_hi"]]
    write_table(hourly, "estimator_a_hourly")

    # Clipped-gap false-positive baseline, measured where true curtailment ~ 0
    # (calibration months, outside the curtailment-prone midday window).
    local = df["ts_utc"] - pd.Timedelta(hours=7)
    from src.potential.calibrate import CAL_MONTHS

    unconstrained = (
        live & local.dt.month.isin(CAL_MONTHS) & ~local.dt.hour.between(10, 15)
    )
    baseline = (
        df[unconstrained]
        .groupby("ba_code")[["curt_lo", "curt_mid", "curt_hi"]]
        .mean()
        .rename(columns=lambda c: f"baseline_{c.split('_')[1]}_per_daylight_hour")
    )

    df["year"] = (df["ts_utc"] - pd.Timedelta(hours=7)).dt.year
    df["is_daylight"] = live
    grp = df[usable].groupby(["ba_code", "year"])
    annual = grp.agg(
        actual_mwh=("solar_mw", "sum"),
        curt_lo_mwh=("curt_lo", "sum"),
        curt_mid_mwh=("curt_mid", "sum"),
        curt_hi_mwh=("curt_hi", "sum"),
        daylight_hours=("is_daylight", "sum"),
        usable_hours=("solar_mw", "size"),
    ).reset_index()
    total_hours = df.groupby(["ba_code", "year"]).size().rename("total_hours").reset_index()
    annual = annual.merge(total_hours, on=["ba_code", "year"])
    annual = annual.merge(baseline, left_on="ba_code", right_index=True)
    coverage = annual["usable_hours"] / annual["total_hours"]
    for band in ["lo", "mid", "hi"]:
        bl = annual[f"baseline_{band}_per_daylight_hour"] * annual["daylight_hours"]
        annual[f"baseline_{band}_mwh"] = bl
        annual[f"curt_{band}_mwh"] = (
            (annual[f"curt_{band}_mwh"] - bl).clip(lower=0) / coverage
        )
    annual["actual_mwh"] = annual["actual_mwh"] / coverage
    annual["coverage"] = coverage
    for band in ["lo", "mid", "hi"]:
        annual[f"curt_{band}_pct"] = (
            100
            * annual[f"curt_{band}_mwh"]
            / (annual["actual_mwh"] + annual[f"curt_{band}_mwh"])
        )
    write_table(annual, "estimator_a_annual")
    return annual


if __name__ == "__main__":
    print(run().to_string(index=False))
