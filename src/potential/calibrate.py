"""Phase 2: modeled potential per plant, calibration, holdout validation.

Calibration design (and its honest limits):

- The physical model (src/potential/model.py) is run per plant on the weather
  the estimator can see (NSRDB in real mode; biased/noisy synthetic weather in
  demo mode). Fixed assumptions (tilt, losses, ...) make its *level* wrong per
  plant, so each plant gets one multiplicative scale factor.
- The scale is fit on **presumed-unconstrained months** (monsoon + high-load
  summer + deep winter: Jun-Sep, Dec-Jan), where economic curtailment in the
  Southwest is historically minimal. This presumption is itself an assumption
  and is listed in the paper's "ways this could be wrong" section — if those
  months do contain curtailment, Estimator A is biased LOW (we calibrate away
  real curtailment), which is the conservative direction for our claim.
- A random subset of calibration-eligible plant-months is **held out**; the
  per-plant relative MAE on those months is the reported model quality.
- Hourly residuals (BA level, unconstrained hours only) supply the
  uncertainty band that Estimator A propagates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.potential.model import plant_potential_ac_mw
from src.store import connect, write_table

CAL_MONTHS = (6, 7, 8, 9, 12, 1)  # presumed unconstrained
HOLDOUT_FRACTION = 0.3
RESIDUAL_QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)


def modeled_potential_all_plants() -> pd.DataFrame:
    """Run the physical model for every plant; persist potential_plant_hour."""
    with connect(read_only=True) as con:
        fleet = con.execute("SELECT * FROM fleet").df()
        weather = con.execute("SELECT * FROM weather_obs").df()

    frames = []
    for _, plant in fleet.iterrows():
        w = weather[weather["plant_id"] == plant["plant_id"]].copy()
        w.index = pd.DatetimeIndex(w["ts_utc"], tz="UTC")
        w = w.sort_index()
        pot = plant_potential_ac_mw(plant, w[["ghi", "dni", "dhi", "temp_air"]])
        frames.append(
            pd.DataFrame(
                {
                    "plant_id": plant["plant_id"],
                    "ts_utc": w["ts_utc"].to_numpy(),
                    "potential_mw_raw": pot.to_numpy(),
                }
            )
        )
    out = pd.concat(frames, ignore_index=True)
    write_table(out, "potential_plant_hour")
    return out


def calibrate(seed: int = 7) -> pd.DataFrame:
    """Per-plant scale factors + holdout MAE; persists `calibration` and
    `potential_monthly_validation`."""
    rng = np.random.default_rng(seed)
    with connect(read_only=True) as con:
        pot = con.execute(
            """
            SELECT plant_id,
                   EXTRACT(year  FROM ts_utc - INTERVAL 7 HOUR) AS year,
                   EXTRACT(month FROM ts_utc - INTERVAL 7 HOUR) AS month,
                   SUM(potential_mw_raw) AS potential_mwh
            FROM potential_plant_hour GROUP BY 1, 2, 3
            """
        ).df()
        gen = con.execute("SELECT * FROM monthly_plant_gen").df()

    m = pot.merge(gen, on=["plant_id", "year", "month"], how="inner")
    m = m[(m["potential_mwh"] > 0) & (m["net_gen_mwh"] > 0)]
    m["eligible"] = m["month"].isin(CAL_MONTHS)
    m["holdout"] = m["eligible"] & (rng.random(len(m)) < HOLDOUT_FRACTION)

    rows, val_rows = [], []
    for plant_id, g in m.groupby("plant_id"):
        train = g[g["eligible"] & ~g["holdout"]]
        hold = g[g["holdout"]]
        scale = train["net_gen_mwh"].sum() / train["potential_mwh"].sum()
        pred_hold = hold["potential_mwh"] * scale
        mae_pct = (
            100 * (pred_hold - hold["net_gen_mwh"]).abs().div(hold["net_gen_mwh"]).mean()
            if len(hold)
            else np.nan
        )
        rows.append(
            {
                "plant_id": plant_id,
                "scale": scale,
                "n_train_months": len(train),
                "n_holdout_months": len(hold),
                "holdout_mae_pct": mae_pct,
            }
        )
        g = g.assign(pred_mwh=g["potential_mwh"] * scale)
        val_rows.append(g)

    cal = pd.DataFrame(rows)
    write_table(cal, "calibration")
    write_table(pd.concat(val_rows, ignore_index=True), "potential_monthly_validation")
    return cal


def ba_potential_and_residuals() -> pd.DataFrame:
    """Calibrated BA-level hourly potential + unconstrained-hour residuals.

    Residual = (potential_cal - actual) / potential_cal on daylight,
    non-imputed hours in calibration months OUTSIDE the curtailment-prone
    midday window. Its quantiles feed Estimator A's uncertainty band.
    Persists `potential_ba_hour` and `residual_quantiles`.
    """
    with connect(read_only=True) as con:
        ba_pot = con.execute(
            """
            SELECT f.ba_code, p.ts_utc,
                   SUM(p.potential_mw_raw * c.scale) AS potential_mw_cal
            FROM potential_plant_hour p
            JOIN fleet f USING (plant_id)
            JOIN calibration c USING (plant_id)
            GROUP BY 1, 2
            """
        ).df()
        actual = con.execute("SELECT * FROM hourly_ba_solar").df()

    merged = ba_pot.merge(actual, on=["ba_code", "ts_utc"], how="inner")
    write_table(
        merged[["ba_code", "ts_utc", "potential_mw_cal", "solar_mw", "is_imputed"]],
        "potential_ba_hour",
    )

    local = merged["ts_utc"] - pd.Timedelta(hours=7)
    daylight = merged["potential_mw_cal"] > 0.05 * merged.groupby("ba_code")[
        "potential_mw_cal"
    ].transform("max")
    unconstrained = (
        local.dt.month.isin(CAL_MONTHS)
        & ~local.dt.hour.between(10, 15)
        & daylight
        & ~merged["is_imputed"].fillna(True).astype(bool)
    )
    sub = merged[unconstrained]
    rel = (sub["potential_mw_cal"] - sub["solar_mw"]) / sub["potential_mw_cal"]

    rows = []
    for ba, g in rel.groupby(sub["ba_code"]):
        for q in RESIDUAL_QUANTILES:
            rows.append({"ba_code": ba, "quantile": q, "rel_residual": g.quantile(q)})
    quants = pd.DataFrame(rows)
    write_table(quants, "residual_quantiles")
    return quants


def run() -> None:
    modeled_potential_all_plants()
    cal = calibrate()
    quants = ba_potential_and_residuals()
    print(cal.to_string(index=False))
    print(quants.pivot(index="ba_code", columns="quantile", values="rel_residual"))


if __name__ == "__main__":
    run()
