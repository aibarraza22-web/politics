"""EIA-860 Arizona utility-scale solar fleet (real mode).

VERIFIED LIVE 2026-07-07 against eia8602024.zip: sheet names
(`2___Plant_Y2024.xlsx`, `3_3_Solar_Y2024.xlsx`, one header row to skip) and
every column below match. Live inspection also showed the solar sheet
includes CSP generators (e.g. parabolic trough — Arizona's Solana), which a
PV model must not ingest: we filter Technology == 'Solar Photovoltaic'.
The sheet carries per-generator Tilt/Azimuth Angle; we deliberately keep the
model's fixed assumptions instead (per-plant calibration absorbs the level
error) — revisit if holdout MAE is poor.
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

    solar = solar[
        (solar["State"] == "AZ")
        & (solar["Status"] == "OP")
        & (solar["Technology"] == "Solar Photovoltaic")
    ]
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
        per_gen.dropna(subset=["capacity_mw_ac"])
        .groupby(["plant_id", "plant_name"], as_index=False)
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


def generator_capacities(year: int) -> pd.DataFrame:
    """Per-generator (plant_id, in_service, capacity_mw_ac) for AZ PV.

    Live 860 data shows phased build-outs (e.g. Eleven Mile, Sonoran): a
    plant's available capacity ramps as generators enter service. The
    potential model scales each plant's modeled output by the in-service
    capacity fraction over time.
    """
    zf = download(year)
    name = next(n for n in zf.namelist() if "3_3_Solar" in n)
    solar = pd.read_excel(zf.open(name), skiprows=1)
    solar = solar[
        (solar["State"] == "AZ")
        & (solar["Status"] == "OP")
        & (solar["Technology"] == "Solar Photovoltaic")
    ]
    return pd.DataFrame(
        {
            "plant_id": solar["Plant Code"],
            "in_service": pd.to_datetime(
                solar["Operating Year"].astype(str)
                + "-"
                + solar["Operating Month"].astype(str).str.zfill(2)
                + "-01",
                errors="coerce",
            ),
            "capacity_mw_ac": pd.to_numeric(solar["Nameplate Capacity (MW)"], errors="coerce"),
        }
    ).dropna().reset_index(drop=True)
