"""Synthetic fixture generator — DEMO MODE ONLY.

Everything this module produces is synthetic and is tagged as such. It exists
for two honest purposes:

1. **Pipeline validation with known ground truth.** It injects a known
   curtailment schedule into a synthetic Arizona-like fleet, then produces the
   observables the real pipeline would see (EIA-930-like hourly BA series with
   imputed hours, EIA-923-like monthly plant generation, NSRDB-like weather
   with measurement error, WEIM-like prices). The estimators must recover the
   injected truth within their stated uncertainty — a real methods test.
2. **Running the full repo end-to-end in environments without data access**
   (CI, sandboxes) so every figure and the paper stay executable.

Realism knobs deliberately included so recovery is *not* trivial:
- the estimator never sees the true weather (per-plant bias + hourly noise),
- plants have outages/derates the estimator is not told about,
- reported series carry measurement noise and imputed hours,
- inverter clipping caps sunny-hour potential,
- economic curtailment mostly (not always) coincides with negative prices.

No number produced here is ever an estimate of actual Arizona curtailment.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config import INTERIM_DIR
from src.potential.model import decompose_ghi, plant_potential_ac_mw
from src.store import write_table

TZ = "Etc/GMT+7"  # Arizona: fixed UTC-7, no DST

DEMO_PLANTS = [
    # plant_id, name, ba, lat, lon, ac_mw, dc_mw, tracking, in_service
    (90001, "Demo Agave Solar", "AZPS", 33.35, -112.90, 300.0, 390.0, "single_axis", "2021-06-01"),
    (90002, "Demo Saguaro Mesa", "AZPS", 32.95, -112.70, 150.0, 195.0, "single_axis", "2019-11-01"),
    (90003, "Demo Sonoran Flats", "AZPS", 33.45, -113.20, 65.0, 84.5, "fixed", "2015-04-01"),
    (90004, "Demo Gila Bend PV", "AZPS", 32.90, -112.45, 32.0, 41.6, "fixed", "2013-07-01"),
    (90005, "Demo Salt River Sun", "SRP", 33.30, -111.60, 200.0, 260.0, "single_axis",
     "2022-01-01"),
    (90006, "Demo Superstition", "SRP", 33.40, -111.45, 100.0, 130.0, "single_axis", "2018-05-01"),
    (90007, "Demo Santa Cruz Sol", "TEPC", 32.10, -110.80, 120.0, 156.0, "single_axis",
     "2020-09-01"),
    (90008, "Demo Avra Valley", "TEPC", 32.35, -111.30, 35.0, 45.5, "fixed", "2012-12-01"),
]

# Injected economic-curtailment fraction of midday potential, by year. The
# upward ramp mimics the oversupply growth story the real analysis tests for.
ECON_FRAC_BY_YEAR = {2022: 0.05, 2023: 0.09, 2024: 0.14}
ECON_MONTHS = (2, 3, 4, 5, 10, 11)  # shoulder seasons
ECON_HOURS = range(10, 16)  # local time
ECON_DAY_SHARE = 0.45  # share of eligible days that actually curtail
PHYS_EVENTS_PER_BA_YEAR = 15


@dataclass
class DemoData:
    fleet: pd.DataFrame
    weather_obs: pd.DataFrame  # what the estimator sees (biased + noisy)
    hourly_ba: pd.DataFrame  # EIA-930-like, with imputed hours flagged
    monthly_plant: pd.DataFrame  # EIA-923-like
    eim_prices: pd.DataFrame  # WEIM-like
    truth_ba_hour: pd.DataFrame  # injected ground truth (never an input!)
    demo_anchors: pd.DataFrame  # Estimator-C-like statements derived from truth
    tables: dict = field(default_factory=dict)


def _fleet() -> pd.DataFrame:
    return pd.DataFrame(
        DEMO_PLANTS,
        columns=[
            "plant_id",
            "plant_name",
            "ba_code",
            "latitude",
            "longitude",
            "capacity_mw_ac",
            "capacity_mw_dc",
            "tracking",
            "in_service",
        ],
    ).assign(source="demo-synthetic")


def _true_weather(index: pd.DatetimeIndex, plant: pd.Series, rng: np.random.Generator,
                  daily_clearness: pd.Series) -> pd.DataFrame:
    """Clear-sky GHI x daily clearness x hourly jitter, plus a temp cycle."""
    from pvlib.location import Location

    loc = Location(plant["latitude"], plant["longitude"], tz=TZ)
    cs = loc.get_clearsky(index, model="ineichen", linke_turbidity=3.0)
    kt = daily_clearness.reindex(index.normalize()).to_numpy()
    jitter = np.clip(rng.normal(1.0, 0.06, len(index)), 0.6, 1.15)
    ghi = (cs["ghi"].to_numpy() * np.clip(kt * jitter, 0.03, 1.05)).clip(min=0)

    doy = index.dayofyear.to_numpy()
    hod = index.hour.to_numpy()
    temp = (
        22
        + 12 * np.sin(2 * np.pi * (doy - 105) / 365)
        + 8 * np.sin(2 * np.pi * (hod - 9) / 24)
        + rng.normal(0, 1.5, len(index))
    )
    w = decompose_ghi(pd.Series(ghi, index=index), plant["latitude"], plant["longitude"])
    w["temp_air"] = temp
    return w


def _daily_clearness(days: pd.DatetimeIndex, rng: np.random.Generator) -> pd.Series:
    """Regional daily clearness index; monsoon (Jul-Sep) is cloudier."""
    monsoon = days.month.isin([7, 8, 9])
    a = np.where(monsoon, 4.0, 9.0)
    b = np.where(monsoon, 2.0, 1.0)
    return pd.Series(rng.beta(a, b), index=days).clip(0.05, 1.0)


def _econ_curtailment_frac(index: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Injected economic curtailment fraction per hour (of available output)."""
    frac = np.zeros(len(index))
    eligible_days = pd.DatetimeIndex(
        d for d in index.normalize().unique() if d.month in ECON_MONTHS
    )
    active = set(
        eligible_days[rng.random(len(eligible_days)) < ECON_DAY_SHARE].to_pydatetime()
    )
    hour_shape = {10: 0.5, 11: 0.8, 12: 1.0, 13: 1.0, 14: 0.8, 15: 0.5}
    day_norm = index.normalize()
    for i, ts in enumerate(index):
        if ts.hour in ECON_HOURS and day_norm[i].to_pydatetime() in active:
            base = ECON_FRAC_BY_YEAR.get(ts.year, 0.0)
            frac[i] = min(0.6, base * hour_shape[ts.hour] * rng.uniform(0.5, 1.8))
    return frac


def _phys_curtailment_frac(index: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    frac = np.zeros(len(index))
    for year in index.year.unique():
        year_idx = np.flatnonzero(index.year == year)
        for _ in range(PHYS_EVENTS_PER_BA_YEAR):
            start = rng.choice(year_idx)
            if index[start].hour < 7 or index[start].hour > 17:
                continue  # events only matter in daylight; skip some randomly
            length = rng.integers(2, 7)
            cut = rng.uniform(0.3, 0.7)
            frac[start : start + length] = np.maximum(frac[start : start + length], cut)
    return frac


def _availability(index: pd.DatetimeIndex, rng: np.random.Generator) -> np.ndarray:
    """Unobserved outages/derates: a few multi-day derate windows per year."""
    avail = np.ones(len(index))
    for year in index.year.unique():
        year_idx = np.flatnonzero(index.year == year)
        for _ in range(rng.integers(2, 5)):
            start = rng.choice(year_idx)
            days = int(rng.integers(2, 10))
            level = rng.uniform(0.3, 0.9)
            avail[start : start + days * 24] = level
    return avail


def _impute_hours(series: pd.Series, rng: np.random.Generator) -> tuple[pd.Series, np.ndarray]:
    """Replace ~0.8% of hours (in runs) with stale values, flagged imputed."""
    flagged = np.zeros(len(series), dtype=bool)
    n_runs = max(1, int(len(series) * 0.008 / 8))
    out = series.copy()
    for _ in range(n_runs):
        start = int(rng.integers(24, len(series) - 24))
        length = int(rng.integers(3, 13))
        flagged[start : start + length] = True
        out.iloc[start : start + length] = series.iloc[start - 24 : start - 24 + length].to_numpy()
    return out, flagged


def generate(years: tuple[int, int] = (2022, 2024), seed: int = 42) -> DemoData:
    rng = np.random.default_rng(seed)
    fleet = _fleet()
    index = pd.date_range(
        f"{years[0]}-01-01 00:00", f"{years[1]}-12-31 23:00", freq="1h", tz=TZ
    )
    daily_kt = _daily_clearness(index.normalize().unique(), rng)

    # Per-BA injected curtailment fractions (applied fleet-wide within the BA).
    ba_codes = sorted(fleet["ba_code"].unique())
    econ = {ba: _econ_curtailment_frac(index, rng) for ba in ba_codes}
    phys = {ba: _phys_curtailment_frac(index, rng) for ba in ba_codes}

    weather_obs_frames, plant_true = [], {}
    for _, plant in fleet.iterrows():
        w_true = _true_weather(index, plant, rng, daily_kt)
        potential = plant_potential_ac_mw(plant, w_true)
        avail = _availability(index, rng)
        plant_true[plant["plant_id"]] = pd.DataFrame(
            {"potential_mw": potential, "avail": avail}, index=index
        )
        # Observed (NSRDB-like) weather: per-plant bias + hourly noise on GHI.
        bias = 1 + rng.normal(0, 0.02)
        noise = np.clip(rng.normal(1.0, 0.04, len(index)), 0.7, 1.3)
        ghi_obs = (w_true["ghi"] * bias * noise).clip(lower=0)
        w_obs = decompose_ghi(ghi_obs, plant["latitude"], plant["longitude"])
        w_obs["temp_air"] = w_true["temp_air"] + rng.normal(0, 1.0, len(index))
        weather_obs_frames.append(
            w_obs.assign(plant_id=plant["plant_id"]).reset_index(names="ts")
        )

    hourly_rows, truth_rows, monthly_rows = [], [], []
    for ba in ba_codes:
        ba_plants = fleet[fleet["ba_code"] == ba]
        curt_frac = np.minimum(0.95, econ[ba] + phys[ba])
        is_phys = phys[ba] > 0
        gen_sum = np.zeros(len(index))
        curt_mwh = np.zeros(len(index))
        pot_mwh = np.zeros(len(index))
        for _, plant in ba_plants.iterrows():
            pt = plant_true[plant["plant_id"]]
            available_mw = pt["potential_mw"].to_numpy() * pt["avail"].to_numpy()
            curtailed = available_mw * curt_frac
            gen = available_mw - curtailed
            gen_sum += gen
            curt_mwh += curtailed
            pot_mwh += available_mw
            g = pd.Series(gen, index=index)
            monthly = g.groupby([g.index.year, g.index.month]).sum()
            for (yr, mo), val in monthly.items():
                monthly_rows.append(
                    {
                        "plant_id": plant["plant_id"],
                        "year": yr,
                        "month": mo,
                        "net_gen_mwh": val * (1 + rng.normal(0, 0.005)),
                    }
                )
        reported = pd.Series(gen_sum * (1 + rng.normal(0, 0.015, len(index))), index=index)
        reported, imputed = _impute_hours(reported, rng)
        hourly_rows.append(
            pd.DataFrame(
                {
                    "ba_code": ba,
                    "ts": index,
                    "solar_mw": reported.clip(lower=0).to_numpy(),
                    "is_imputed": imputed,
                }
            )
        )
        truth_rows.append(
            pd.DataFrame(
                {
                    "ba_code": ba,
                    "ts": index,
                    "true_curtailment_mwh": curt_mwh,
                    "true_available_mwh": pot_mwh,
                    "curtailment_type": np.where(
                        curt_mwh <= 0, "none", np.where(is_phys, "physical", "economic")
                    ),
                }
            )
        )

    # WEIM-like prices: negative during most economic-curtailment hours,
    # sometimes negative without curtailment, often NOT negative during
    # physical events (that is the honest failure mode of Estimator B).
    price_rows = []
    for ba in ba_codes:
        hod = index.hour.to_numpy()
        base = 28 + 14 * np.sin(2 * np.pi * (hod - 16) / 24) + rng.normal(0, 6, len(index))
        econ_hours = econ[ba] > 0
        neg_draw = rng.random(len(index))
        price = base.copy()
        goes_neg = econ_hours & (neg_draw < 0.9)
        price[goes_neg] = -rng.uniform(1, 25, goes_neg.sum())
        false_neg = (~econ_hours) & (hod >= 10) & (hod <= 15) & (neg_draw < 0.03)
        price[false_neg] = -rng.uniform(0.5, 8, false_neg.sum())
        price_rows.append(pd.DataFrame({"ba_code": ba, "ts": index, "lmp_usd_mwh": price}))

    truth = pd.concat(truth_rows, ignore_index=True)
    anchors = _demo_anchors(truth, rng)

    data = DemoData(
        fleet=fleet,
        weather_obs=pd.concat(weather_obs_frames, ignore_index=True),
        hourly_ba=pd.concat(hourly_rows, ignore_index=True),
        monthly_plant=pd.DataFrame(monthly_rows),
        eim_prices=pd.concat(price_rows, ignore_index=True),
        truth_ba_hour=truth,
        demo_anchors=anchors,
    )
    return data


def _demo_anchors(truth: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Estimator-C-like documented statements, derived from truth with error.

    Mimics the real anchors' looseness: annual, rounded, sometimes only one
    BA, quoted with +/-15% relative error against the true value.
    """
    rows = []
    t = truth.assign(year=truth["ts"].dt.year)
    for ba, year in [("AZPS", 2023), ("TEPC", 2024), ("SRP", 2024)]:
        g = t[(t["ba_code"] == ba) & (t["year"] == year)]
        true_pct = 100 * g["true_curtailment_mwh"].sum() / g["true_available_mwh"].sum()
        stated = round(true_pct * (1 + rng.normal(0, 0.15)), 1)
        rows.append(
            {
                "anchor_id": f"demo-{ba.lower()}-{year}",
                "utility": f"Demo {ba}",
                "ba_code": ba,
                "period_start": f"{year}-01-01",
                "period_end": f"{year}-12-31",
                "curtailment_value": stated,
                "unit": "percent_of_available",
                "curtailment_type": "unspecified",
                "source_title": "SYNTHETIC demo anchor (derived from injected truth)",
                "source_url": "demo://synthetic",
                "exact_quote": f"[synthetic] Approximately {stated}% of available solar "
                f"energy was curtailed in {year}.",
                "retrieved_date": "",
                "notes": "DEMO MODE ONLY — generated by src/demo_data.py, not a real filing.",
            }
        )
    return pd.DataFrame(rows)


def persist(data: DemoData) -> None:
    """Write all demo tables to parquet (data/interim/demo/) and duckdb."""
    out = INTERIM_DIR / "demo"
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "fleet": data.fleet,
        "weather_obs": data.weather_obs,
        "hourly_ba_solar": data.hourly_ba,
        "monthly_plant_gen": data.monthly_plant,
        "eim_prices": data.eim_prices,
        "demo_truth_ba_hour": data.truth_ba_hour,
        "demo_anchors": data.demo_anchors,
    }
    for name, df in tables.items():
        df = df.copy()
        for col in df.columns:
            if isinstance(df[col].dtype, pd.DatetimeTZDtype):
                df[col] = df[col].dt.tz_convert("UTC").dt.tz_localize(None)
                df = df.rename(columns={col: f"{col}_utc"})
        df.to_parquet(out / f"{name}.parquet", index=False)
        write_table(df, name)


if __name__ == "__main__":
    persist(generate())
    print("demo fixtures written")
