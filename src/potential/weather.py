"""Real-mode hourly weather at plant locations.

Preferred source is NREL NSRDB (research-grade satellite irradiance), but
this session's network policy does not allowlist developer.nrel.gov, so the
wired source is **Open-Meteo's ERA5-blend archive** (verified live
2026-07-07): hourly shortwave_radiation (GHI), direct_normal_irradiance,
diffuse_radiation, temperature_2m, no key, one request per point covering
the whole date range.

Honesty notes (also in SOURCES.md `weather`):
- ERA5-based irradiance is coarser (~9-25 km) and has known biases vs NSRDB.
  Per-plant calibration absorbs the level error; the residual band carries
  the rest. Swap in NSRDB (fetch_nsrdb_psm3) when the domain is reachable
  and compare — a cheap robustness check the paper should report.
- Open-Meteo hourly radiation is the mean of the preceding hour; we shift
  labels by -1h so rows are hour-beginning UTC, matching the repo
  convention.
"""

from __future__ import annotations

import time

import pandas as pd
import requests

from src.config import RAW_DIR

OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
HOURLY_VARS = "shortwave_radiation,direct_normal_irradiance,diffuse_radiation,temperature_2m"


def fetch_open_meteo(
    plant_id: int, lat: float, lon: float, start: str, end: str
) -> pd.DataFrame:
    """Hourly ghi/dni/dhi/temp_air for one plant, hour-beginning UTC. Cached."""
    cache = RAW_DIR / "weather_openmeteo" / f"{plant_id}_{start}_{end}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    for attempt in range(10):
        try:
            resp = requests.get(
                OPEN_METEO_URL,
                params={
                    "latitude": round(lat, 4),
                    "longitude": round(lon, 4),
                    "start_date": start,
                    "end_date": end,
                    "hourly": HOURLY_VARS,
                    "timezone": "UTC",
                },
                timeout=120,
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # volume throttling often shows up as a hung connection
            time.sleep(60 * (attempt + 1))
            continue
        if resp.status_code == 429:
            time.sleep(60 * (attempt + 1))
            continue
        resp.raise_for_status()
        h = resp.json()["hourly"]
        df = pd.DataFrame(
            {
                # radiation values are preceding-hour means: label -1h =
                # hour-beginning of the interval they describe
                "ts_utc": pd.to_datetime(h["time"]) - pd.Timedelta(hours=1),
                "ghi": h["shortwave_radiation"],
                "dni": h["direct_normal_irradiance"],
                "dhi": h["diffuse_radiation"],
                "temp_air": h["temperature_2m"],
            }
        ).dropna(subset=["ghi"])
        df[["ghi", "dni", "dhi"]] = df[["ghi", "dni", "dhi"]].clip(lower=0)
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache, index=False)
        time.sleep(1.5)
        return df
    raise RuntimeError(f"Open-Meteo kept rate-limiting plant {plant_id}")


def fetch_fleet_weather(fleet: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """weather_obs table (plant_id, ts_utc, ghi, dni, dhi, temp_air) for a fleet."""
    frames = []
    for _, p in fleet.iterrows():
        w = fetch_open_meteo(int(p["plant_id"]), p["latitude"], p["longitude"], start, end)
        w = w.assign(plant_id=int(p["plant_id"]))
        frames.append(w)
    return pd.concat(frames, ignore_index=True)[
        ["ts_utc", "ghi", "dni", "dhi", "temp_air", "plant_id"]
    ]


def fetch_nsrdb_psm3(plant_id: int, lat: float, lon: float, year: int) -> pd.DataFrame:
    """Preferred NSRDB path — requires developer.nrel.gov to be reachable and
    NREL_API_KEY/NREL_API_EMAIL set. Same output schema as fetch_open_meteo."""
    import io

    from src.config import api_key

    cache = RAW_DIR / "weather_nsrdb" / f"{plant_id}_{year}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    resp = requests.get(
        "https://developer.nrel.gov/api/nsrdb/v2/solar/psm3-2-2-download.csv",
        params={
            "api_key": api_key("NREL_API_KEY"),
            "email": api_key("NREL_API_EMAIL"),
            "wkt": f"POINT({lon} {lat})",
            "names": str(year),
            "attributes": "ghi,dni,dhi,air_temperature",
            "interval": "60",
            "utc": "true",
        },
        timeout=600,
    )
    resp.raise_for_status()
    df = pd.read_csv(io.BytesIO(resp.content), skiprows=2)
    out = pd.DataFrame(
        {
            "ts_utc": pd.to_datetime(
                df[["Year", "Month", "Day", "Hour", "Minute"]]
            ),
            "ghi": df["GHI"],
            "dni": df["DNI"],
            "dhi": df["DHI"],
            "temp_air": df["Temperature"],
        }
    )
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache, index=False)
    return out
