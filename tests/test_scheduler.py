import numpy as np
import pandas as pd
import pytest

from src.computeflex.scheduler import DCConfig, Result, schedule


def make_surplus(hours=24 * 21, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-02", periods=hours, freq="1h")
    hod = idx.hour.to_numpy()
    midday = (hod >= 10) & (hod <= 15)
    s = np.where(midday, rng.uniform(0, 200, hours), 0.0)
    return pd.Series(s, index=idx)


def cfg(**kw) -> DCConfig:
    base = dict(it_mw=100.0, flexibility="fully_deferrable", sla_frac=0.7)
    base.update(kw)
    return DCConfig(**base)


def test_energy_conservation_and_bounds():
    res = schedule(make_surplus(), cfg())
    assert isinstance(res, Result)
    assert 0 <= res.surplus_share <= 1
    assert 0 <= res.absorbed_frac <= 1
    assert res.surplus_served_mwh <= res.dc_energy_mwh + 1e-6


def test_sla_is_met():
    c = cfg(sla_frac=0.7)
    res = schedule(make_surplus(), c)
    # capacity factor ~ SLA (overhead energy is extra, not load)
    assert res.capacity_factor == pytest.approx(0.7, abs=0.02)


def test_firm_has_full_capacity_factor_and_no_restarts():
    res = schedule(make_surplus(), cfg(flexibility="firm", sla_frac=0.5))
    assert res.capacity_factor == pytest.approx(1.0)
    assert res.n_restarts == 0


def test_flexibility_ordering():
    """More flexibility can never serve less surplus at the same SLA."""
    s = make_surplus()
    shares = {
        f: schedule(s, cfg(flexibility=f, sla_frac=0.7)).surplus_share
        for f in ("firm", "partially_deferrable", "fully_deferrable")
    }
    assert shares["fully_deferrable"] >= shares["partially_deferrable"] - 1e-9
    assert shares["partially_deferrable"] >= shares["firm"] - 1e-9


def test_battery_never_hurts():
    s = make_surplus()
    no_batt = schedule(s, cfg()).surplus_share
    batt = schedule(s, cfg(battery_power_mw=50, battery_energy_mwh=200)).surplus_share
    assert batt >= no_batt - 1e-9


def test_higher_checkpoint_cost_raises_effective_cost():
    s = make_surplus()
    cheap = schedule(s, cfg(), checkpoint_frac=0.0)
    dear = schedule(s, cfg(), checkpoint_frac=0.2)
    assert dear.effective_cost_usd_mwh >= cheap.effective_cost_usd_mwh


def test_zero_surplus_means_zero_share():
    idx = pd.date_range("2023-01-02", periods=24 * 7, freq="1h")
    res = schedule(pd.Series(0.0, index=idx), cfg())
    assert res.surplus_share == 0
