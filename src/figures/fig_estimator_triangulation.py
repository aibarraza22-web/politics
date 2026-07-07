"""figure_id: fig-estimator-triangulation

The three-estimator comparison, by BA and year, in a common unit (% of
available solar energy). Nothing is averaged:

- Estimator A: point (median) with 5-95% residual-propagation band,
- Estimator B: downward triangle = UPPER BOUND (economic signal only),
- Estimator C: diamonds = documented anchors, in their native percent unit,
- demo mode only: X = injected ground truth (the recovery test).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from src.figures.style import INK, INK_2, SERIES, demo_banner, save, style_axes
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-estimator-triangulation"


def build(figures_dir=None):
    mode = pipeline_mode()
    with connect(read_only=True) as con:
        a = con.execute("SELECT * FROM estimator_a_annual ORDER BY ba_code, year").df()
        b = con.execute("SELECT * FROM estimator_b_annual ORDER BY ba_code, year").df()
        c = con.execute(
            "SELECT * FROM estimator_c_anchors WHERE unit = 'percent_of_available'"
        ).df()
        truth = None
        if mode == "demo":
            truth = con.execute(
                """
                SELECT ba_code, EXTRACT(year FROM ts_utc - INTERVAL 7 HOUR) AS year,
                       100 * SUM(true_curtailment_mwh) / SUM(true_available_mwh) AS pct
                FROM demo_truth_ba_hour GROUP BY 1, 2
                HAVING SUM(true_available_mwh) > 1000
                """
            ).df()

    bas = sorted(set(a["ba_code"]) | set(b["ba_code"]))
    all_years = np.array(sorted(set(a["year"].astype(int)) | set(b["year"].astype(int))))
    fig, axes = plt.subplots(1, len(bas), figsize=(10.5, 3.9), dpi=200, sharey=True)
    for ax, ba in zip(np.atleast_1d(axes), bas, strict=True):
        style_axes(ax)
        ga = a[a["ba_code"] == ba]
        yrs = ga["year"].to_numpy() if len(ga) else all_years
        if not len(ga):
            ax.text(
                0.5, 0.94,
                "A: n/a — 930 series not\nattributable to modeled fleet",
                transform=ax.transAxes, ha="center", va="top", fontsize=7.5,
                color="#8a1c1c",
            )
        ax.errorbar(
            yrs - 0.08,
            ga["curt_mid_pct"],
            yerr=[
                ga["curt_mid_pct"] - ga["curt_lo_pct"],
                ga["curt_hi_pct"] - ga["curt_mid_pct"],
            ],
            fmt="o",
            color=SERIES[0],
            markersize=5,
            capsize=3,
            linewidth=1.5,
            label="A: potential gap (5–95%)",
        )
        gb = b[b["ba_code"] == ba]
        ax.scatter(
            gb["year"] + 0.08,
            gb["upper_bound_pct"],
            marker="v",
            s=45,
            color=SERIES[2],
            label="B: neg-price upper bound",
            zorder=3,
        )
        gc = c[c["ba_code"] == ba]
        if len(gc):
            ax.scatter(
                gc["year"],
                gc["curtailment_value"],
                marker="D",
                s=40,
                facecolors="none",
                edgecolors=SERIES[3],
                linewidths=1.4,
                label="C: documented anchor",
                zorder=4,
            )
        if truth is not None:
            gt = truth[truth["ba_code"] == ba]
            ax.scatter(
                gt["year"],
                gt["pct"],
                marker="x",
                s=55,
                color=INK,
                linewidths=1.6,
                label="injected truth (demo)",
                zorder=5,
            )
        ax.set_title(ba, fontsize=10, color=INK)
        ax.set_xticks(yrs)
        ax.set_xlim(yrs.min() - 0.6, yrs.max() + 0.6)
    np.atleast_1d(axes)[0].set_ylabel("Curtailment (% of available energy)", color=INK_2)
    np.atleast_1d(axes)[0].set_ylim(bottom=0)
    handles, labels = np.atleast_1d(axes)[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=4, frameon=False, fontsize=8,
        bbox_to_anchor=(0.5, -0.06),
    )
    fig.tight_layout()
    demo_banner(fig, mode)
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
