"""Estimator B — WEIM negative/zero-price market signal.

What negative prices can and cannot say: a zero/negative locational price
marks an hour where the market cleared with surplus — an *economic*
curtailment signal. It is an HOURS-based signal; converting hours to energy
requires the coincident potential, which gives only an UPPER BOUND (you
cannot curtail more than was available). Physical (grid-constrained)
curtailment often shows no price signal at all, so B is expected to sit
below A. This is stated, not smoothed over.

Real mode — VERIFIED LIVE 2026-07-07 (see SOURCES.md `oasis`):
- Report: `PRC_INTVL_LMP` (RTM, 5-minute) via SingleZip, resultformat=6.
  Rows repeat per LMP_TYPE (LMP/MCC/MCE/MCL); the price column is named
  literally "MW". Filter LMP_TYPE == 'LMP'.
- Arizona EIM Load Aggregation Points (probed live; wrong names return an
  .xml error member instead of a .csv): ELAP_AZPS-APND, ELAP_SRP-APND,
  ELAP_TEPC-APND.
- DATA AVAILABILITY (bisected live): ELAP_* price data exists on OASIS only
  from ~2023-04-01 onward — nothing in 2022 or Jan-Mar 2023, under any
  naming variant we probed. Estimator B therefore covers Apr-2023+ on real
  data, and the triangulation must say so.
- SPAN LIMIT (probed live): requests for this 5-min report fail beyond ~1
  week; we chunk by 7 days.
- 5-min prices are averaged to hour-beginning UTC hours for analysis.
"""

from __future__ import annotations

import io
import time
import zipfile

import pandas as pd

from src.config import RAW_DIR
from src.store import connect, write_table

OASIS_BASE = "https://oasis.caiso.com/oasisapi/SingleZip"
OASIS_QUERY = "PRC_INTVL_LMP"
EIM_NODES = {"AZPS": "ELAP_AZPS-APND", "SRP": "ELAP_SRP-APND", "TEPC": "ELAP_TEPC-APND"}
NEG_THRESHOLD = 0.0  # $/MWh; hours at or below count as surplus signal
_SLEEP_S = 5  # OASIS rate limiting is aggressive


EIM_DATA_START = "2023-04-01"  # bisected live; nothing published before this
_CHUNK_DAYS = 7  # span limit probed live


def _node_cache(node: str, start: pd.Timestamp, end: pd.Timestamp):
    return RAW_DIR / "oasis" / f"{node}_{start:%Y%m%d}_{end:%Y%m%d}.parquet"


def _fetch_chunk_all_nodes(start: pd.Timestamp, end: pd.Timestamp) -> None:
    """One <=7-day chunk of 5-min RTM LMPs for ALL three AZ ELAPs in a single
    request (OASIS accepts comma-separated node lists — one round trip
    instead of three; OASIS responses run tens of seconds each). Results are
    split into per-node parquet caches."""
    nodes = list(EIM_NODES.values())
    missing = [n for n in nodes if not _node_cache(n, start, end).exists()]
    if not missing:
        return
    params = {
        "queryname": OASIS_QUERY,
        "startdatetime": start.strftime("%Y%m%dT00:00-0000"),
        "enddatetime": end.strftime("%Y%m%dT00:00-0000"),
        "version": "1",
        "market_run_id": "RTM",
        "node": ",".join(nodes),
        "resultformat": "6",
    }
    import requests

    for attempt in range(6):
        resp = requests.get(OASIS_BASE, params=params, timeout=600)
        if resp.status_code == 429:
            time.sleep(30 * (attempt + 1))
            continue
        resp.raise_for_status()
        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        member = zf.namelist()[0]
        if member.endswith(".xml"):  # OASIS error payload
            raise RuntimeError(f"OASIS error for {start:%Y%m%d}: {member}")
        df = pd.read_csv(zf.open(member))
        df = df[df["LMP_TYPE"] == "LMP"]
        for node, g in df.groupby("NODE"):
            out = pd.DataFrame(
                {
                    "ts5_utc": pd.to_datetime(
                        g["INTERVALSTARTTIME_GMT"]
                    ).dt.tz_localize(None),
                    "lmp_usd_mwh": pd.to_numeric(g["MW"], errors="coerce"),
                }
            ).sort_values("ts5_utc")
            cache = _node_cache(str(node), start, end)
            cache.parent.mkdir(parents=True, exist_ok=True)
            out.to_parquet(cache, index=False)
        time.sleep(_SLEEP_S)
        return
    raise RuntimeError(f"OASIS kept rate-limiting chunk {start:%Y%m%d}")


def fetch_eim_prices(start: str = EIM_DATA_START, end: str = "2024-12-31") -> pd.DataFrame:
    """Hourly (hour-beginning UTC) mean RTM LMP per BA, chunked + cached."""
    edges = pd.date_range(start, pd.Timestamp(end) + pd.Timedelta(days=1),
                          freq=f"{_CHUNK_DAYS}D")
    if edges[-1] < pd.Timestamp(end) + pd.Timedelta(days=1):
        edges = edges.append(pd.DatetimeIndex([pd.Timestamp(end) + pd.Timedelta(days=1)]))
    from concurrent.futures import ThreadPoolExecutor

    chunks = list(zip(edges[:-1], edges[1:], strict=False))
    # OASIS responses take tens of seconds server-side; a few parallel
    # workers cut wall time without hammering the rate limit (429s still
    # back off per worker).
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda c: _fetch_chunk_all_nodes(*c), chunks))

    frames = []
    for s, e in chunks:
        for ba, node in EIM_NODES.items():
            five_min = pd.read_parquet(_node_cache(node, s, e))
            hourly = (
                five_min.set_index("ts5_utc")
                .resample("1h")["lmp_usd_mwh"]
                .mean()
                .dropna()
                .reset_index()
                .rename(columns={"ts5_utc": "ts_utc"})
            )
            hourly.insert(0, "ba_code", ba)
            frames.append(hourly)
    out = pd.concat(frames, ignore_index=True)
    return out.drop_duplicates(subset=["ba_code", "ts_utc"]).reset_index(drop=True)


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
    # The hours-based signal is price-only and valid for every BA; the ENERGY
    # bound divides by the 930 actual, which is only meaningful where the 930
    # series reconciles with the modeled fleet (not AZPS — see pipeline).
    from src.pipeline import pipeline_mode, reconciled_ba_codes

    if pipeline_mode() == "real":
        bad = ~annual["ba_code"].isin(reconciled_ba_codes())
        annual.loc[bad, ["upper_bound_mwh", "upper_bound_pct"]] = float("nan")
    write_table(annual, "estimator_b_annual")
    return annual


if __name__ == "__main__":
    print(run().to_string(index=False))
