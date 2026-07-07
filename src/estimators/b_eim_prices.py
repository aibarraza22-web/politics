"""Estimator B — WEIM negative/zero-price market signal.

What negative prices can and cannot say: a zero/negative locational price
marks an hour where the market cleared with surplus — an *economic*
curtailment signal. It is an HOURS-based signal; converting hours to energy
requires the coincident potential, which gives only an UPPER BOUND (you
cannot curtail more than was available). Physical (grid-constrained)
curtailment often shows no price signal at all, so B is expected to sit
below A. This is stated, not smoothed over.

Real mode: fetch_oasis_prices() targets CAISO OASIS SingleZip. STATUS:
unverified-live — report name and AZ node naming MUST be investigated on the
live OASIS site and recorded in SOURCES.md `oasis` before trusting anything
it returns (SPEC.md says do not trust the spec on this).
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd

from src.store import connect, write_table

OASIS_BASE = "https://oasis.caiso.com/oasisapi/SingleZip"
# Candidate report per OASIS docs; VERIFY against live OASIS before use.
OASIS_QUERY = "PRC_INTVL_LMP"
NEG_THRESHOLD = 0.0  # $/MWh; hours at or below count as surplus signal


def fetch_oasis_prices(start: str, end: str, node: str) -> pd.DataFrame:
    """Real-mode fetcher (unverified-live; see module docstring)."""
    import requests

    params = {
        "queryname": OASIS_QUERY,
        "startdatetime": f"{start}T08:00-0000",
        "enddatetime": f"{end}T08:00-0000",
        "version": "1",
        "market_run_id": "RTM",
        "node": node,
        "resultformat": "6",  # CSV
    }
    resp = requests.get(OASIS_BASE, params=params, timeout=300)
    resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    return pd.read_csv(zf.open(zf.namelist()[0]))


def run() -> pd.DataFrame:
    """Annual negative-price statistics per BA from the `eim_prices` table."""
    with connect(read_only=True) as con:
        df = con.execute(
            """
            SELECT p.ba_code, p.ts_utc, p.lmp_usd_mwh,
                   b.potential_mw_cal, b.solar_mw, b.is_imputed
            FROM eim_prices p
            LEFT JOIN potential_ba_hour b USING (ba_code, ts_utc)
            """
        ).df()

    df["year"] = (df["ts_utc"] - pd.Timedelta(hours=7)).dt.year
    peak = df.groupby("ba_code")["potential_mw_cal"].transform("max")
    df["daylight"] = df["potential_mw_cal"] > 0.05 * peak
    df["neg"] = df["lmp_usd_mwh"] <= NEG_THRESHOLD

    grp = df.groupby(["ba_code", "year"])
    annual = grp.apply(
        lambda g: pd.Series(
            {
                "neg_hours": int(g["neg"].sum()),
                "neg_daylight_hours": int((g["neg"] & g["daylight"]).sum()),
                "daylight_hours": int(g["daylight"].sum()),
                "mean_neg_depth_usd": -g.loc[g["neg"], "lmp_usd_mwh"].mean(),
                # Upper bound on economically-curtailed energy: all coincident
                # potential during negative daylight hours.
                "upper_bound_mwh": g.loc[g["neg"] & g["daylight"], "potential_mw_cal"].sum(),
                "actual_mwh": g["solar_mw"].sum(),
            }
        ),
        include_groups=False,
    ).reset_index()
    annual["neg_share_of_daylight_pct"] = (
        100 * annual["neg_daylight_hours"] / annual["daylight_hours"]
    )
    annual["upper_bound_pct"] = (
        100 * annual["upper_bound_mwh"] / (annual["actual_mwh"] + annual["upper_bound_mwh"])
    )
    write_table(annual, "estimator_b_annual")
    return annual


if __name__ == "__main__":
    print(run().to_string(index=False))
