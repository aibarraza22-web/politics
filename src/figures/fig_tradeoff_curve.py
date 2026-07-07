"""figure_id: fig-tradeoff-curve

Headline figure: utilization (capacity factor, set by the weekly SLA) vs.
share of data-center energy served by otherwise-curtailed surplus, per
flexibility class (100 MW IT, no battery, Estimator A mid band). The
whisker on the reference point carries Estimator A's lo-hi band through the
simulation — estimation uncertainty, not operational tuning, dominates.
"""

from __future__ import annotations

from src.computeflex.scenarios import REFERENCE
from src.figures.style import INK, INK_2, SERIES, demo_banner, new_axes, save
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-tradeoff-curve"

LABELS = {
    "fully_deferrable": "fully deferrable (optimistic envelope)",
    "partially_deferrable": "partially deferrable (realistic anchor)",
    "firm": "firm (no flexibility)",
}
COLORS = {
    "fully_deferrable": SERIES[0],
    "partially_deferrable": SERIES[1],
    "firm": SERIES[2],
}


def build(figures_dir=None):
    with connect(read_only=True) as con:
        grid = con.execute(
            """
            SELECT * FROM computeflex_scenarios
            WHERE it_mw = 100 AND battery_h = 0 AND band = 'mid'
            ORDER BY flexibility, sla_frac
            """
        ).df()
        ref = con.execute(
            f"""
            SELECT band, surplus_share, capacity_factor FROM computeflex_scenarios
            WHERE it_mw = {REFERENCE["it_mw"]}
              AND flexibility = '{REFERENCE["flexibility"]}'
              AND sla_frac = {REFERENCE["sla_frac"]} AND battery_h = 0
            """
        ).df()

    fig, ax = new_axes(figsize=(7.6, 4.4))
    for flex, g in grid.groupby("flexibility"):
        ax.plot(
            100 * g["capacity_factor"],
            100 * g["surplus_share"],
            marker="o",
            markersize=5,
            linewidth=2,
            color=COLORS[flex],
        )
        first = g.iloc[0]
        dy = {"fully_deferrable": 10, "partially_deferrable": -16, "firm": 12}[flex]
        ax.annotate(
            LABELS[flex],
            xy=(100 * first["capacity_factor"], 100 * first["surplus_share"]),
            xytext=(4, dy),
            textcoords="offset points",
            fontsize=8.5,
            color=COLORS[flex],
            fontweight="bold",
            ha="left",
        )

    r = ref.set_index("band")
    if {"lo", "mid", "hi"} <= set(r.index):
        ax.errorbar(
            100 * r.loc["mid", "capacity_factor"],
            100 * r.loc["mid", "surplus_share"],
            yerr=[
                [100 * (r.loc["mid", "surplus_share"] - r.loc["lo", "surplus_share"])],
                [100 * (r.loc["hi", "surplus_share"] - r.loc["mid", "surplus_share"])],
            ],
            fmt="s",
            color=INK,
            markersize=6,
            capsize=4,
            linewidth=1.4,
        )
        ax.annotate(
            "reference scenario,\nEstimator A lo–hi band",
            xy=(100 * r.loc["mid", "capacity_factor"], 100 * r.loc["hi", "surplus_share"]),
            xytext=(8, 4),
            textcoords="offset points",
            fontsize=8,
            color=INK_2,
        )

    ax.set_xlabel("Capacity factor achieved (%)", color=INK_2)
    ax.set_ylabel("DC energy served by surplus (%)", color=INK_2)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    demo_banner(fig, pipeline_mode())
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
