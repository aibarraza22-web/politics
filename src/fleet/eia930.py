"""EIA-930 hourly solar generation per BA.

VERIFIED LIVE 2026-07-07 (see SOURCES.md `eia930`):

- v2 API route `electricity/rto/fuel-type-data` returns
  {respondent, period "YYYY-MM-DDTHH" (UTC), value (MWh), fueltype} — matches
  the original parser, but carries NO imputation flags. Cross-checked
  against the bulk file: the API's hourly `period` label is the hour
  ENDING (API "T20" == bulk interval 19:00-20:00 UTC).
- Grid Monitor bulk balance CSVs
  (`.../gridmonitor/sixMonthFiles/EIA930_BALANCE_{year}_{Jan_Jun|Jul_Dec}.csv`)
  carry, per BA-hour: "Net Generation (MW) from Solar" (reported),
  "... (Imputed)" (non-empty exactly when EIA imputed the hour), and
  "... (Adjusted)" (EIA's published series). Header inspected live.
- SCHEMA DRIFT (inspected live): 2024 Jul_Dec onward uses a 65-column layout
  that splits solar into "Solar without Integrated Battery Storage" and
  "Solar with Integrated Battery Storage" — including a typo in EIA's own
  header ("Solar witho Integrated Battery Storage (Adjusted)"). We match
  solar columns by regex (tolerating the typo), sum the split series, and
  flag the hour imputed if any component was imputed.

Primary source is therefore the bulk CSV: value = Adjusted solar,
is_imputed = Imputed column non-null. The API fetcher remains as a
cross-check. Timestamps: the CSV gives UTC *end* of hour; we store
hour-beginning (`ts_utc = end - 1h`) repo-wide.
"""

from __future__ import annotations

import pandas as pd
import requests

from src.config import RAW_DIR
from src.fleet.eia_api import get_paged

BA_CODES = ("AZPS", "SRP", "TEPC")
ROUTE = "electricity/rto/fuel-type-data"
BULK_URL = (
    "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/"
    "EIA930_BALANCE_{year}_{half}.csv"
)
SOLAR_COL = "Net Generation (MW) from Solar"


import re

# Matches "Solar", "Solar without Integrated Battery Storage", and EIA's own
# typo "Solar witho Integrated Battery Storage".
_SOLAR_RE = re.compile(
    r"^Net Generation \(MW\) from Solar"
    r"( w\w* Integrated Battery Storage)?\s*"
    r"(\((?P<variant>Imputed|Adjusted)\))?$"
)


def _solar_cols(columns) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"reported": [], "Imputed": [], "Adjusted": []}
    for c in columns:
        m = _SOLAR_RE.match(c.strip())
        if m:
            out[m.group("variant") or "reported"].append(c)
    return out


def _download_bulk(year: int, half: str) -> pd.DataFrame:
    """Download one six-month balance file, normalized to
    (ba_code, end_utc, solar_mw_adjusted, is_imputed). Cached to parquet."""
    cache = RAW_DIR / f"eia930_balance_{year}_{half}_v2.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    url = BULK_URL.format(year=year, half=half)
    resp = requests.get(url, timeout=900)
    resp.raise_for_status()
    from io import BytesIO

    df = pd.read_csv(BytesIO(resp.content), thousands=",", low_memory=False)
    cols = _solar_cols(df.columns)
    if not cols["Adjusted"] or not cols["Imputed"]:
        raise RuntimeError(
            f"EIA930 bulk {year} {half}: no solar Adjusted/Imputed columns found in "
            f"{len(df.columns)}-col header: {list(df.columns)[:8]}..."
        )
    df = df[df["Balancing Authority"].isin(BA_CODES)]
    adjusted = (
        df[cols["Adjusted"]].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=1)
    )
    imputed_any = df[cols["Imputed"]].apply(pd.to_numeric, errors="coerce").notna().any(axis=1)
    out = pd.DataFrame(
        {
            "ba_code": df["Balancing Authority"].to_numpy(),
            "end_utc": pd.to_datetime(
                df["UTC Time at End of Hour"], format="%m/%d/%Y %I:%M:%S %p"
            ).to_numpy(),
            "solar_mw": adjusted.to_numpy(),
            "is_imputed": imputed_any.to_numpy(),
        }
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache, index=False)
    return out


def fetch_hourly_solar_bulk(
    years: tuple[int, ...], ba_codes: tuple[str, ...] = BA_CODES
) -> pd.DataFrame:
    frames = []
    for year in years:
        for half in ("Jan_Jun", "Jul_Dec"):
            frames.append(_download_bulk(year, half))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["ba_code"].isin(ba_codes)]
    out = pd.DataFrame(
        {
            "ba_code": df["ba_code"],
            "ts_utc": df["end_utc"] - pd.Timedelta(hours=1),
            "solar_mw": df["solar_mw"],
            "is_imputed": df["is_imputed"].astype(bool),
        }
    )
    # Hours where even the adjusted value is missing are unusable: flag them.
    out.loc[out["solar_mw"].isna(), "is_imputed"] = True
    return (
        out.drop_duplicates(subset=["ba_code", "ts_utc"])
        .sort_values(["ba_code", "ts_utc"])
        .reset_index(drop=True)
    )


def fetch_hourly_solar_api(
    start: str, end: str, ba_codes: tuple[str, ...] = BA_CODES
) -> pd.DataFrame:
    """v2 API cross-check series (no imputation flags — is_imputed = NA)."""
    rows = get_paged(
        ROUTE,
        {
            "frequency": "hourly",
            "data[0]": "value",
            "facets[respondent][]": list(ba_codes),
            "facets[fueltype][]": ["SUN"],
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
        },
    )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"EIA-930 API returned no rows for {ba_codes} {start}..{end}")
    return pd.DataFrame(
        {
            "ba_code": df["respondent"],
            "ts_utc": pd.to_datetime(df["period"]),
            "solar_mw": pd.to_numeric(df["value"], errors="coerce"),
            "is_imputed": pd.NA,
        }
    ).sort_values(["ba_code", "ts_utc"]).reset_index(drop=True)
