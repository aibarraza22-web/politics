"""EIA-930 hourly solar generation per BA (real mode).

STATUS: unverified-live (no network route from this build environment); see
src/fleet/eia_api.py and SOURCES.md `eia930`.

Known limitation to resolve at live verification: the v2 API route
`electricity/rto/fuel-type-data` serves post-processed values and does NOT
carry the imputation flags that the Grid Monitor bulk balance CSVs have.
Until the bulk-CSV path is added, rows fetched here get `is_imputed = NULL`
(unknown) — downstream code treats unknown as "handle explicitly", never as
"clean". Demo mode provides explicit flags. Do not silently ingest.
"""

from __future__ import annotations

import pandas as pd

from src.fleet.eia_api import get_paged

BA_CODES = ("AZPS", "SRP", "TEPC")
ROUTE = "electricity/rto/fuel-type-data"


def fetch_hourly_solar(
    start: str, end: str, ba_codes: tuple[str, ...] = BA_CODES
) -> pd.DataFrame:
    """Hourly UTC solar net generation (MWh -> MW) for the given BAs."""
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
        raise RuntimeError(f"EIA-930 returned no rows for {ba_codes} {start}..{end}")
    out = pd.DataFrame(
        {
            "ba_code": df["respondent"],
            "ts_utc": pd.to_datetime(df["period"], utc=True).dt.tz_localize(None),
            "solar_mw": pd.to_numeric(df["value"], errors="coerce"),
            "is_imputed": pd.NA,  # unknown via v2 API; see module docstring
        }
    )
    return out.sort_values(["ba_code", "ts_utc"]).reset_index(drop=True)
