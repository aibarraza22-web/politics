"""Flexible data center scheduling simulation (Phase 4).

Model: a data center with IT capacity `it_mw` and power usage effectiveness
`pue` draws `it_mw * pue` MW at full load. Its flexibility class fixes the
floor it can never shed:

- fully_deferrable: floor 0.0 (pure batch training, checkpoint + stop)
- partially_deferrable: floor 0.5
- firm: floor 1.0 (no flexibility; the comparison baseline)

Each ISO week must deliver `sla_frac` of the energy a full-tilt week would
deliver (the job-completion SLA). The greedy scheduler serves the floor every
hour, then places the flexible portion into the hours with the most surplus
first. Every contiguous flexible-run start pays a checkpoint/restart energy
overhead. An optional battery charges from otherwise-unabsorbed surplus and
discharges into non-surplus DC load (round-trip losses applied).

The simulation consumes an hourly surplus series (Estimator A's band of
choice) and never invents surplus. All prices/parameters live in
ASSUMPTIONS or the scenario grid — one visible table, per the honesty rules.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

ASSUMPTIONS = {
    "flat_tariff_usd_mwh": 45.0,
    "surplus_energy_price_usd_mwh": 5.0,
    "checkpoint_overhead_frac": 0.05,  # of one full-load hour, per restart
    "battery_rt_efficiency": 0.85,
    "pue": 1.2,
}

FLEX_FLOOR = {"fully_deferrable": 0.0, "partially_deferrable": 0.5, "firm": 1.0}


@dataclass
class DCConfig:
    it_mw: float
    flexibility: str  # key of FLEX_FLOOR
    sla_frac: float  # weekly energy SLA vs full-tilt week
    pue: float = ASSUMPTIONS["pue"]
    battery_power_mw: float = 0.0
    battery_energy_mwh: float = 0.0

    @property
    def full_load_mw(self) -> float:
        return self.it_mw * self.pue

    @property
    def floor_mw(self) -> float:
        return FLEX_FLOOR[self.flexibility] * self.full_load_mw


@dataclass
class Result:
    surplus_share: float  # fraction of DC energy served by surplus
    capacity_factor: float
    absorbed_frac: float  # fraction of all surplus energy absorbed
    effective_cost_usd_mwh: float
    dc_energy_mwh: float
    surplus_served_mwh: float
    n_restarts: int


def schedule(surplus_mw: pd.Series, cfg: DCConfig,
             tariff: float | None = None,
             surplus_price: float | None = None,
             checkpoint_frac: float | None = None,
             battery_eff: float | None = None) -> Result:
    """Greedy weekly scheduling of the flexible load into surplus hours."""
    tariff = ASSUMPTIONS["flat_tariff_usd_mwh"] if tariff is None else tariff
    surplus_price = (
        ASSUMPTIONS["surplus_energy_price_usd_mwh"] if surplus_price is None else surplus_price
    )
    checkpoint_frac = (
        ASSUMPTIONS["checkpoint_overhead_frac"] if checkpoint_frac is None else checkpoint_frac
    )
    battery_eff = ASSUMPTIONS["battery_rt_efficiency"] if battery_eff is None else battery_eff

    s = surplus_mw.fillna(0).clip(lower=0)
    idx = s.index
    load = np.full(len(s), cfg.floor_mw)
    flex_mw = cfg.full_load_mw - cfg.floor_mw

    if flex_mw > 0:
        iso = idx.isocalendar()
        week = pd.Series(iso.week.to_numpy() + 100 * iso.year.to_numpy(), index=idx)
        for _, widx in s.groupby(week).groups.items():
            positions = idx.get_indexer(widx)
            need_mwh = cfg.sla_frac * cfg.full_load_mw * len(positions)
            need_mwh -= cfg.floor_mw * len(positions)
            if need_mwh <= 0:
                continue
            order = positions[np.argsort(-s.iloc[positions].to_numpy(), kind="stable")]
            n_full = int(need_mwh // flex_mw)
            load[order[:n_full]] += flex_mw
            rem = need_mwh - n_full * flex_mw
            if rem > 0 and n_full < len(order):
                load[order[n_full]] += rem

    running = load > cfg.floor_mw + 1e-9
    n_restarts = int(((~np.roll(running, 1)) & running)[1:].sum() + (1 if running[0] else 0))
    overhead_mwh = n_restarts * checkpoint_frac * cfg.full_load_mw

    surplus_served = np.minimum(s.to_numpy(), load)
    grid_served = load - surplus_served

    # Battery: charge from leftover surplus, discharge against grid-served load.
    if cfg.battery_power_mw > 0 and cfg.battery_energy_mwh > 0:
        soc = 0.0
        leftover = s.to_numpy() - surplus_served
        for i in range(len(load)):
            charge = min(leftover[i], cfg.battery_power_mw, cfg.battery_energy_mwh - soc)
            soc += charge
            discharge = min(grid_served[i], cfg.battery_power_mw, soc) * battery_eff
            soc -= discharge / battery_eff
            grid_served[i] -= discharge
            surplus_served[i] += discharge

    dc_energy = float(load.sum()) + overhead_mwh
    surplus_mwh = float(surplus_served.sum())
    grid_mwh = dc_energy - surplus_mwh
    cost = surplus_mwh * surplus_price + grid_mwh * tariff
    total_surplus = float(s.sum())
    return Result(
        surplus_share=surplus_mwh / dc_energy if dc_energy else 0.0,
        capacity_factor=float(load.mean()) / cfg.full_load_mw if cfg.full_load_mw else 0.0,
        absorbed_frac=surplus_mwh / total_surplus if total_surplus else 0.0,
        effective_cost_usd_mwh=cost / dc_energy if dc_energy else 0.0,
        dc_energy_mwh=dc_energy,
        surplus_served_mwh=surplus_mwh,
        n_restarts=n_restarts,
    )
