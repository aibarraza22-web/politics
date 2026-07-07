"""Tracking-aware pvlib potential model, per plant.

One function maps (plant row, hourly weather) -> modeled AC potential in MW.
The same code path serves both modes: real weather from NSRDB (Phase 2) and
synthetic weather from the demo fixture generator. Unknown per-plant
parameters (tilt, GCR, losses) are fixed assumptions listed in
ASSUMPTIONS and reported in the paper's assumptions table; per-plant
calibration (Estimator A) absorbs their average error, and the calibration
residual distribution carries the rest into the uncertainty bands.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pvlib
from pvlib.location import Location

ASSUMPTIONS = {
    "fixed_tilt_deg": 25.0,
    "fixed_azimuth_deg": 180.0,
    "tracker_gcr": 0.35,
    "tracker_max_angle_deg": 60.0,
    "pvwatts_losses_frac": 0.14,
    "gamma_pdc_per_degc": -0.0035,
    "dc_ac_ratio_default": 1.3,
    "albedo": 0.2,
}


def _poa(plant: pd.Series, solpos: pd.DataFrame, weather: pd.DataFrame) -> pd.Series:
    dni_extra = pvlib.irradiance.get_extra_radiation(weather.index)
    if plant["tracking"] == "single_axis":
        tr = pvlib.tracking.singleaxis(
            solpos["apparent_zenith"],
            solpos["azimuth"],
            axis_azimuth=180.0,
            max_angle=ASSUMPTIONS["tracker_max_angle_deg"],
            backtrack=True,
            gcr=ASSUMPTIONS["tracker_gcr"],
        )
        tilt = tr["surface_tilt"].fillna(0)
        azim = tr["surface_azimuth"].fillna(180)
    else:
        tilt = pd.Series(ASSUMPTIONS["fixed_tilt_deg"], index=weather.index)
        azim = pd.Series(ASSUMPTIONS["fixed_azimuth_deg"], index=weather.index)

    total = pvlib.irradiance.get_total_irradiance(
        tilt,
        azim,
        solpos["apparent_zenith"],
        solpos["azimuth"],
        weather["dni"],
        weather["ghi"],
        weather["dhi"],
        dni_extra=dni_extra,
        albedo=ASSUMPTIONS["albedo"],
        model="haydavies",
    )
    return total["poa_global"].fillna(0).clip(lower=0)


def plant_potential_ac_mw(plant: pd.Series, weather: pd.DataFrame) -> pd.Series:
    """Modeled AC potential (MW) for one plant on an hourly weather frame.

    `plant` needs: latitude, longitude, capacity_mw_ac, capacity_mw_dc,
    tracking ('fixed'|'single_axis'). `weather` needs a tz-aware
    DatetimeIndex and columns ghi, dni, dhi, temp_air (°C).
    """
    loc = Location(plant["latitude"], plant["longitude"])
    solpos = loc.get_solarposition(weather.index)
    poa = _poa(plant, solpos, weather)

    temp_cell = pvlib.temperature.faiman(poa, weather["temp_air"])
    pdc0_mw = plant["capacity_mw_dc"]
    if not np.isfinite(pdc0_mw) or pdc0_mw <= 0:
        pdc0_mw = plant["capacity_mw_ac"] * ASSUMPTIONS["dc_ac_ratio_default"]

    dc_mw = pvlib.pvsystem.pvwatts_dc(
        poa, temp_cell, pdc0_mw, gamma_pdc=ASSUMPTIONS["gamma_pdc_per_degc"]
    )
    ac_mw = dc_mw * (1 - ASSUMPTIONS["pvwatts_losses_frac"])
    # Inverter clipping at AC nameplate: real fleets clip, and clipping is a
    # confounder Estimator A must not mistake for curtailment.
    return ac_mw.clip(lower=0, upper=plant["capacity_mw_ac"]).rename("potential_ac_mw")


def decompose_ghi(ghi: pd.Series, latitude: float, longitude: float) -> pd.DataFrame:
    """GHI-only weather -> (ghi, dni, dhi) via the Erbs model.

    Used by the demo generator, which synthesizes only GHI; NSRDB provides
    measured components directly.
    """
    loc = Location(latitude, longitude)
    solpos = loc.get_solarposition(ghi.index)
    erbs = pvlib.irradiance.erbs(ghi, solpos["zenith"], ghi.index)
    out = pd.DataFrame({"ghi": ghi, "dni": erbs["dni"], "dhi": erbs["dhi"]})
    return out.fillna(0).clip(lower=0)
