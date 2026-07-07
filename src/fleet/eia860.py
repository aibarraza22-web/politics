"""EIA-860 Arizona utility-scale solar fleet (real mode).

STATUS: unverified-live (no network route from this build environment).
Parses the annual EIA-860 zip's `2___Plant_Y{year}.xlsx` (lat/lon) and
`3_3_Solar_Y{year}.xlsx` (capacity, tracking) sheets. Column names below are
from the published 2023 layout; the first networked run MUST diff them
against the real workbook (EIA renames columns between vintages) and record
findings in SOURCES.md `eia860`.
"""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import requests

from src.config import RAW_DIR

URL_TEMPLATE = "https://www.eia.gov/electricity/data/eia860/xls/eia860{year}.zip"


def download(year: int) -> zipfile.ZipFile:
    cache = RAW_DIR / f"eia860_{year}.zip"
    if not cache.exists():
        resp = requests.get(URL_TEMPLATE.format(year=year), timeout=600)
        resp.raise_for_status()
        cache.write_bytes(resp.content)
    return zipfile.ZipFile(io.BytesIO(cache.read_bytes()))


def build_az_solar_fleet(year: int) -> pd.DataFrame:
    zf = download(year)

    def read(name_part: str) -> pd.DataFrame:
        name = next(n for n in zf.namelist() if name_part in n)
        return pd.read_excel(zf.open(name), skiprows=1)

    plants = read("2___Plant")
    solar = read("3_3_Solar")

    solar = solar[(solar["State"] == "AZ") & (solar["Status"] == "OP")]
    tracking = pd.Series("fixed", index=solar.index)
    tracking[solar["Single-Axis Tracking?"].eq("Y")] = "single_axis"
    tracking[solar["Dual-Axis Tracking?"].eq("Y")] = "dual_axis"

    per_gen = pd.DataFrame(
        {
            "plant_id": solar["Plant Code"],
            "plant_name": solar["Plant Name"],
            "capacity_mw_ac": pd.to_numeric(solar["Nameplate Capacity (MW)"], errors="coerce"),
            "capacity_mw_dc": pd.to_numeric(
                solar.get("DC Net Capacity (MW)"), errors="coerce"
            ),
            "tracking": tracking,
            "in_service": pd.to_datetime(
                solar["Operating Year"].astype(str)
                + "-"
                + solar["Operating Month"].astype(str).str.zfill(2)
                + "-01",
                errors="coerce",
            ),
        }
    )
    fleet = (
        per_gen.groupby(["plant_id", "plant_name"], as_index=False)
        .agg(
            capacity_mw_ac=("capacity_mw_ac", "sum"),
            capacity_mw_dc=("capacity_mw_dc", "sum"),
            tracking=("tracking", lambda s: s.mode().iat[0]),
            in_service=("in_service", "min"),
        )
        .merge(
            plants[["Plant Code", "Latitude", "Longitude", "Balancing Authority Code"]]
            .rename(
                columns={
                    "Plant Code": "plant_id",
                    "Latitude": "latitude",
                    "Longitude": "longitude",
                    "Balancing Authority Code": "ba_code",
                }
            ),
            on="plant_id",
            how="left",
        )
        .assign(source=f"eia860-{year}")
    )
    return fleet[fleet["capacity_mw_ac"] >= 1.0].reset_index(drop=True)
