"""figure_id: fig-negative-price-hours

Estimator B's raw signal: monthly count of zero/negative-price daylight
hours per BA. One line per BA (fixed slot colors), direct labels at the
line ends.
"""

from __future__ import annotations

from src.estimators.b_eim_prices import NEG_THRESHOLD
from src.figures.style import BA_COLORS, INK_2, demo_banner, new_axes, save
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-negative-price-hours"


def build(figures_dir=None):
    with connect(read_only=True) as con:
        df = con.execute(
            f"""
            SELECT p.ba_code,
                   DATE_TRUNC('month', p.ts_utc - INTERVAL 7 HOUR) AS month,
                   SUM(CASE WHEN p.lmp_usd_mwh <= {NEG_THRESHOLD} THEN 1 ELSE 0 END) AS neg_hours
            FROM eim_prices p GROUP BY 1, 2 ORDER BY 1, 2
            """
        ).df()

    fig, ax = new_axes(figsize=(8.2, 3.9))
    for ba, g in df.groupby("ba_code"):
        ax.plot(g["month"], g["neg_hours"], color=BA_COLORS[ba], linewidth=2)
        last = g.iloc[-1]
        ax.annotate(
            ba,
            xy=(last["month"], last["neg_hours"]),
            xytext=(6, 0),
            textcoords="offset points",
            fontsize=9,
            color=BA_COLORS[ba],
            fontweight="bold",
            va="center",
        )
    ax.set_ylabel("Hours with price ≤ $0/MWh (per month)", color=INK_2)
    ax.set_xlabel("Month", color=INK_2)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    demo_banner(fig, pipeline_mode())
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
