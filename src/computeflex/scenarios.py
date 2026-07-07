"""Phase 4 scenario grid + tornado sensitivity.

Surplus input: statewide (AZPS+SRP+TEPC) hourly series from Estimator A.
The scenario grid never mixes bands: each scenario names the band it used.
The skeptical case is explicit: frontier-training-realistic flexibility is
NOT fully deferrable — `partially_deferrable` with a high SLA is the
realistic anchor scenario, and the fully-deferrable rows are labeled as the
optimistic envelope.
"""

from __future__ import annotations

import itertools

import pandas as pd

from src.computeflex.scheduler import ASSUMPTIONS, DCConfig, schedule
from src.store import connect, write_table

DC_SIZES_MW = (50.0, 100.0, 200.0)
FLEX_CLASSES = ("fully_deferrable", "partially_deferrable", "firm")
SLA_LEVELS = (0.5, 0.7, 0.9)
BATTERY_OPTIONS = (0.0, 4.0)  # battery hours at half IT power; 0 = none
BANDS = ("lo", "mid", "hi")
REFERENCE = {
    "it_mw": 100.0,
    "flexibility": "partially_deferrable",
    "sla_frac": 0.9,
    "battery_h": 0.0,
    "band": "mid",
}


def statewide_surplus(band: str) -> pd.Series:
    with connect(read_only=True) as con:
        df = con.execute(
            f"""
            SELECT ts_utc, SUM(curt_{band}) AS surplus_mw
            FROM estimator_a_hourly GROUP BY 1 ORDER BY 1
            """
        ).df()
    return pd.Series(
        df["surplus_mw"].to_numpy(), index=pd.DatetimeIndex(df["ts_utc"])
    ).fillna(0)


def _cfg(it_mw: float, flexibility: str, sla: float, battery_h: float) -> DCConfig:
    return DCConfig(
        it_mw=it_mw,
        flexibility=flexibility,
        sla_frac=sla,
        battery_power_mw=it_mw / 2 if battery_h else 0.0,
        battery_energy_mwh=battery_h * it_mw / 2 if battery_h else 0.0,
    )


def run_grid() -> pd.DataFrame:
    surplus = {band: statewide_surplus(band) for band in BANDS}
    rows = []
    for it_mw, flex, sla, batt_h, band in itertools.product(
        DC_SIZES_MW, FLEX_CLASSES, SLA_LEVELS, BATTERY_OPTIONS, ("mid",)
    ):
        res = schedule(surplus[band], _cfg(it_mw, flex, sla, batt_h))
        rows.append(
            {
                "it_mw": it_mw, "flexibility": flex, "sla_frac": sla,
                "battery_h": batt_h, "band": band,
                **res.__dict__,
            }
        )
    # Reference scenario across all three bands (uncertainty carried through).
    for band in BANDS:
        res = schedule(
            surplus[band],
            _cfg(REFERENCE["it_mw"], REFERENCE["flexibility"], REFERENCE["sla_frac"],
                 REFERENCE["battery_h"]),
        )
        rows.append(
            {
                "it_mw": REFERENCE["it_mw"], "flexibility": REFERENCE["flexibility"],
                "sla_frac": REFERENCE["sla_frac"], "battery_h": REFERENCE["battery_h"],
                "band": band, **res.__dict__,
            }
        )
    grid = pd.DataFrame(rows).drop_duplicates(
        subset=["it_mw", "flexibility", "sla_frac", "battery_h", "band"]
    )
    write_table(grid, "computeflex_scenarios")
    return grid


def run_tornado() -> pd.DataFrame:
    """One-at-a-time sensitivity of the reference scenario's surplus share."""
    surplus_mid = statewide_surplus("mid")
    ref_cfg = _cfg(REFERENCE["it_mw"], REFERENCE["flexibility"], REFERENCE["sla_frac"],
                   REFERENCE["battery_h"])
    base = schedule(surplus_mid, ref_cfg).surplus_share

    perturbations = {
        "Surplus band (A lo … hi)": [
            schedule(statewide_surplus("lo"), ref_cfg).surplus_share,
            schedule(statewide_surplus("hi"), ref_cfg).surplus_share,
        ],
        "SLA 0.7 … 0.95": [
            schedule(surplus_mid, _cfg(100.0, REFERENCE["flexibility"], 0.95, 0.0)).surplus_share,
            schedule(surplus_mid, _cfg(100.0, REFERENCE["flexibility"], 0.7, 0.0)).surplus_share,
        ],
        "Flexibility firm … fully deferrable": [
            schedule(surplus_mid, _cfg(100.0, "firm", REFERENCE["sla_frac"], 0.0)).surplus_share,
            schedule(
                surplus_mid, _cfg(100.0, "fully_deferrable", REFERENCE["sla_frac"], 0.0)
            ).surplus_share,
        ],
        "DC size 200 … 50 MW": [
            schedule(surplus_mid, _cfg(200.0, REFERENCE["flexibility"], REFERENCE["sla_frac"],
                                       0.0)).surplus_share,
            schedule(surplus_mid, _cfg(50.0, REFERENCE["flexibility"], REFERENCE["sla_frac"],
                                       0.0)).surplus_share,
        ],
        "Checkpoint overhead 0 … 15%": [
            schedule(surplus_mid, ref_cfg, checkpoint_frac=0.15).surplus_share,
            schedule(surplus_mid, ref_cfg, checkpoint_frac=0.0).surplus_share,
        ],
        "Battery none … 4h": [
            base,
            schedule(surplus_mid, _cfg(100.0, REFERENCE["flexibility"], REFERENCE["sla_frac"],
                                       4.0)).surplus_share,
        ],
    }
    rows = [
        {"parameter": k, "low": min(v), "high": max(v), "base": base}
        for k, v in perturbations.items()
    ]
    tornado = pd.DataFrame(rows)
    write_table(tornado, "computeflex_tornado")
    return tornado


def persist_assumptions() -> None:
    rows = [{"parameter": k, "value": v} for k, v in ASSUMPTIONS.items()]
    rows += [
        {"parameter": "dc_sizes_mw", "value": str(DC_SIZES_MW)},
        {"parameter": "flexibility_floors", "value": "0.0 / 0.5 / 1.0 of full load"},
        {"parameter": "sla_levels", "value": str(SLA_LEVELS)},
        {"parameter": "battery_options", "value": "none; 4h at IT/2 power"},
        {"parameter": "surplus_source",
         "value": "Estimator A hourly, summed over BAs where A is defensible "
                  "(BAs failing 930-vs-923 reconciliation excluded), band as labeled"},
    ]
    write_table(pd.DataFrame(rows), "scenario_assumptions")


def main() -> None:
    grid = run_grid()
    tornado = run_tornado()
    persist_assumptions()
    print(grid.head(12).to_string(index=False))
    print(tornado.to_string(index=False))


if __name__ == "__main__":
    main()
