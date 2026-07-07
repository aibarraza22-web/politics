"""EIA-923 monthly per-plant solar net generation (real mode).

STATUS: unverified-live (no network route from this build environment); see
src/fleet/eia_api.py and SOURCES.md `eia923`.
"""

from __future__ import annotations

import pandas as pd

from src.fleet.eia_api import get_paged

ROUTE = "electricity/facility-fuel"


def fetch_monthly_plant_gen(start: str, end: str, state: str = "AZ") -> pd.DataFrame:
    rows = get_paged(
        ROUTE,
        {
            "frequency": "monthly",
            "data[0]": "generation",
            "facets[state][]": [state],
            "facets[fuel2002][]": ["SUN"],
            "start": start,
            "end": end,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
        },
    )
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"EIA-923 returned no rows for {state} {start}..{end}")
    period = pd.to_datetime(df["period"])
    return (
        pd.DataFrame(
            {
                "plant_id": pd.to_numeric(df["plantCode"]),
                "year": period.dt.year,
                "month": period.dt.month,
                "net_gen_mwh": pd.to_numeric(df["generation"], errors="coerce"),
            }
        )
        .groupby(["plant_id", "year", "month"], as_index=False)["net_gen_mwh"]
        .sum()
    )
