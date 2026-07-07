"""figure_id: fig-potential-validation

Phase 2 acceptance: calibrated modeled monthly energy vs reported monthly
energy per plant. Holdout months (never used to fit the scale) are the
filled markers; the per-plant relative MAE on holdout months is printed in
the side panel. A perfect model sits on the diagonal.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from src.figures.style import INK, INK_2, SERIES, demo_banner, save, style_axes
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-potential-validation"


def build(figures_dir=None):
    with connect(read_only=True) as con:
        val = con.execute(
            "SELECT * FROM potential_monthly_validation WHERE eligible"
        ).df()
        cal = con.execute(
            "SELECT * FROM calibration ORDER BY holdout_mae_pct DESC"
        ).df()

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(9.5, 4.2), dpi=200, gridspec_kw={"width_ratios": [1.4, 1]}
    )
    style_axes(ax)
    style_axes(ax2)

    lim = max(val["net_gen_mwh"].max(), val["pred_mwh"].max()) * 1.05 / 1000
    ax.plot([0, lim], [0, lim], color=INK_2, linewidth=1, linestyle="--", zorder=1)
    train = val[~val["holdout"]]
    hold = val[val["holdout"]]
    ax.scatter(
        train["net_gen_mwh"] / 1000, train["pred_mwh"] / 1000,
        s=14, facecolors="none", edgecolors=SERIES[0], linewidths=0.8,
        label="calibration months",
    )
    ax.scatter(
        hold["net_gen_mwh"] / 1000, hold["pred_mwh"] / 1000,
        s=16, color=SERIES[3], label="holdout months",
    )
    ax.set_xlabel("Reported monthly energy (GWh)", color=INK_2)
    ax.set_ylabel("Modeled, calibrated (GWh)", color=INK_2)
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    y = np.arange(len(cal))
    ax2.barh(y, cal["holdout_mae_pct"], height=0.6, color=SERIES[0])
    ax2.set_yticks(y, [str(int(p)) for p in cal["plant_id"]], fontsize=8)
    ax2.set_xlabel("Holdout MAE (% of monthly energy)", color=INK_2)
    ax2.set_ylabel("Plant", color=INK_2)
    for yi, v in zip(y, cal["holdout_mae_pct"], strict=True):
        ax2.text(v + 0.05, yi, f"{v:.1f}%", va="center", fontsize=8, color=INK)
    ax2.grid(axis="x", color="#e6e5e0", linewidth=0.8)
    ax2.grid(axis="y", visible=False)

    fig.tight_layout()
    demo_banner(fig, pipeline_mode())
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
