"""NSRDB via the AWS Open Data S3 mirror (no NREL API needed).

developer.nrel.gov rejects this environment's egress IPs, but NREL publishes
the full NSRDB on S3 (`nrel-pds-nsrdb`, anonymous access — verified live
2026-07-07). We read the aggregated 4km/30-min product
(`GOES/aggregated/v4.0.0/nsrdb_{year}.h5`) surgically:

- `meta` latitude/longitude (cached) -> KD-tree nearest site per plant
  (all 89 AZ plants land within 0.025 deg of a cell center);
- plants collapse into 500-site chunk-aligned strips (43 strips), each
  ~18 MB per variable-year, read in parallel;
- 30-min samples -> hourly means labeled hour-beginning UTC, matching the
  repo convention and the Open-Meteo fetcher's schema exactly.

Scale factors come from each dataset's `psm_scale_factor` attribute
(air_temperature is stored x10).
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from src.config import RAW_DIR

BUCKET_KEY = "s3://nrel-pds-nsrdb/GOES/aggregated/v4.0.0/nsrdb_{year}.h5"
VARS = ("ghi", "dni", "dhi", "air_temperature")
BLOCK = 500  # site-axis chunk width in the h5 files
# Processes, not threads: h5py's global HDF5 lock + fsspec's event loop
# deadlock under ThreadPoolExecutor (observed live — worker froze at 54 MB).
_WORKERS = 6


def _open(year: int):
    import h5py
    import s3fs

    fs = s3fs.S3FileSystem(anon=True, default_block_size=8 * 1024 * 1024)
    return h5py.File(fs.open(BUCKET_KEY.format(year=year), "rb"), "r")


def site_map(fleet: pd.DataFrame) -> pd.DataFrame:
    """plant_id -> nearest NSRDB site index (meta lat/lon cached as npy)."""
    from scipy.spatial import cKDTree

    lat_p = RAW_DIR / "nsrdb_meta_lat.npy"
    lon_p = RAW_DIR / "nsrdb_meta_lon.npy"
    if not (lat_p.exists() and lon_p.exists()):
        f = _open(2023)
        np.save(lat_p, f["meta"]["latitude", ::1])
        np.save(lon_p, f["meta"]["longitude", ::1])
    tree = cKDTree(np.c_[np.load(lat_p), np.load(lon_p)])
    dist, idx = tree.query(np.c_[fleet["latitude"], fleet["longitude"]])
    out = fleet[["plant_id"]].copy()
    out["site_idx"] = idx
    out["dist_deg"] = dist
    if out["dist_deg"].max() > 0.06:
        raise RuntimeError("a plant is suspiciously far from any NSRDB cell")
    return out


def _fetch_block(year: int, block: int, site_idx: np.ndarray) -> pd.DataFrame:
    """One 500-site strip for one year: all four variables, needed sites only.
    Cached per (year, block)."""
    cache = RAW_DIR / "nsrdb_s3" / f"{year}_{block}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    lo, hi = block * BLOCK, (block + 1) * BLOCK
    cols = np.unique(site_idx[(site_idx >= lo) & (site_idx < hi)])
    f = _open(year)
    times = pd.to_datetime([t.decode()[:19] for t in f["time_index"][:]])
    data = {}
    for var in VARS:
        d = f[var]
        scale = float(d.attrs.get("psm_scale_factor", 1.0))
        strip = d[:, lo:hi].astype(np.float32) / scale
        for c in cols:
            data[(var, int(c))] = strip[:, int(c) - lo]
    frames = []
    for c in cols:
        frames.append(
            pd.DataFrame(
                {
                    "site_idx": int(c),
                    "ts30_utc": times,
                    "ghi": data[("ghi", int(c))],
                    "dni": data[("dni", int(c))],
                    "dhi": data[("dhi", int(c))],
                    "temp_air": data[("air_temperature", int(c))],
                }
            )
        )
    out = pd.concat(frames, ignore_index=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache, index=False)
    print(f"nsrdb {year} block {block}: {len(cols)} sites", flush=True)
    return out


def _fetch_block_star(args) -> pd.DataFrame:
    return _fetch_block(*args)


def fetch_fleet_weather_nsrdb(fleet: pd.DataFrame, years: tuple[int, ...]) -> pd.DataFrame:
    """weather_obs frame (plant_id, ts_utc hourly, ghi, dni, dhi, temp_air)."""
    smap = site_map(fleet)
    idx = smap["site_idx"].to_numpy()
    tasks = [(y, b, idx) for y in years for b in sorted(set(idx // BLOCK))]
    with ProcessPoolExecutor(max_workers=_WORKERS) as pool:
        results = list(pool.map(_fetch_block_star, tasks))
    long = pd.concat(results, ignore_index=True)

    long["ts_utc"] = long["ts30_utc"].dt.floor("1h")
    hourly = (
        long.groupby(["site_idx", "ts_utc"], as_index=False)[
            ["ghi", "dni", "dhi", "temp_air"]
        ].mean()
    )
    merged = smap.merge(hourly, on="site_idx")
    return merged[["ts_utc", "ghi", "dni", "dhi", "temp_air", "plant_id"]]


if __name__ == "__main__":
    from src.store import connect

    with connect(read_only=True) as con:
        fleet = con.execute("SELECT * FROM fleet").df()
    w = fetch_fleet_weather_nsrdb(fleet, (2022, 2023, 2024))
    w.to_parquet(RAW_DIR / "weather_nsrdb_fleet.parquet", index=False)
    print("done", w.shape, "plants:", w["plant_id"].nunique())
