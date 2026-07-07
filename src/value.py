"""The value layer: what the estimated surplus is worth, in units people act on.

All conversions are single documented assumptions (added to
`scenario_assumptions`), applied to Estimator A's banded annual surplus for
the BAs where A is defensible. Nothing here narrows a band — value ranges
inherit the estimation ranges.

- avoided_cost:    a flexible buyer displaces grid purchases at the flat
                   tariff and pays the surplus price -> $/MWh spread.
- dump_payments:   during negative-price hours, estimated curtailed energy
                   times |price| approximates what producers paid (or forwent)
                   to shed output — computed hour-by-hour from EIM prices x
                   Estimator A's hourly series, so price/surplus coincidence
                   is respected, not assumed. CAVEAT: the hourly series
                   carries the clipped-gap false-positive bias that the
                   ANNUAL totals correct via the unconstrained-hour baseline;
                   dump payments are therefore biased high and labeled
                   indicative, not headline.
- homes:           AZ residential average ~12 MWh/yr.
- co2:             displaced marginal generation in AZ is overwhelmingly gas
                   (~0.42 tCO2/MWh short-run marginal).
"""

from __future__ import annotations

import pandas as pd

from src.computeflex.scheduler import ASSUMPTIONS
from src.store import connect, write_table

VALUE_ASSUMPTIONS = {
    "az_home_mwh_per_year": 12.0,
    "gas_marginal_tco2_per_mwh": 0.42,
}


def run() -> pd.DataFrame:
    spread = (
        ASSUMPTIONS["flat_tariff_usd_mwh"] - ASSUMPTIONS["surplus_energy_price_usd_mwh"]
    )
    with connect(read_only=True) as con:
        annual = con.execute(
            "SELECT ba_code, year, curt_lo_mwh, curt_mid_mwh, curt_hi_mwh "
            "FROM estimator_a_annual"
        ).df()
        dump = con.execute(
            """
            SELECT a.ba_code,
                   CAST(EXTRACT(year FROM a.ts_utc - INTERVAL 7 HOUR) AS INT) AS year,
                   SUM(CASE WHEN p.lmp_usd_mwh <= 0
                       THEN -p.lmp_usd_mwh * COALESCE(a.curt_mid, 0) ELSE 0 END)
                       AS dump_payment_mid_usd,
                   SUM(CASE WHEN p.lmp_usd_mwh <= 0 THEN COALESCE(a.curt_mid, 0)
                       ELSE 0 END) AS neg_hour_surplus_mid_mwh
            FROM estimator_a_hourly a
            JOIN eim_prices p USING (ba_code, ts_utc)
            GROUP BY 1, 2
            """
        ).df()

    out = annual.merge(dump, on=["ba_code", "year"], how="left")
    for band in ("lo", "mid", "hi"):
        out[f"avoided_cost_{band}_usd"] = out[f"curt_{band}_mwh"] * spread
        out[f"homes_{band}"] = out[f"curt_{band}_mwh"] / VALUE_ASSUMPTIONS[
            "az_home_mwh_per_year"
        ]
        out[f"tco2_{band}"] = out[f"curt_{band}_mwh"] * VALUE_ASSUMPTIONS[
            "gas_marginal_tco2_per_mwh"
        ]
    write_table(out, "value_annual")

    rows = [{"parameter": k, "value": v} for k, v in VALUE_ASSUMPTIONS.items()]
    with connect() as con:
        existing = con.execute("SELECT * FROM scenario_assumptions").df()
        merged = pd.concat(
            [existing[~existing["parameter"].isin(VALUE_ASSUMPTIONS)],
             pd.DataFrame(rows).astype({"value": str})],
            ignore_index=True,
        )
    write_table(merged, "scenario_assumptions")
    return out


if __name__ == "__main__":
    df = run()
    cols = ["ba_code", "year", "curt_mid_mwh", "avoided_cost_mid_usd",
            "dump_payment_mid_usd", "homes_mid", "tco2_mid"]
    print(df[cols].round(0).to_string(index=False))
