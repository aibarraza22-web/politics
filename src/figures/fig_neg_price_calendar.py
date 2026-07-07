"""figure_id: fig-neg-price-calendar

The operational product: for each BA, the share of days on which the hourly
mean RTM price at its EIM LAP was <= $0, by month x hour-of-day (MST).
This is the "when to run flexible load" calendar — computed from CAISO's
published prices, Apr-2023 onward (full available history).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from src.estimators.b_eim_prices import NEG_THRESHOLD
from src.figures.style import INK, INK_2, demo_banner, save
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-neg-price-calendar"


def calendar_data():
    with connect(read_only=True) as con:
        return con.execute(
            f"""
            SELECT ba_code,
                   CAST(EXTRACT(month FROM ts_utc - INTERVAL 7 HOUR) AS INT) AS month,
                   CAST(EXTRACT(hour  FROM ts_utc - INTERVAL 7 HOUR) AS INT) AS hour,
                   100.0 * AVG(CASE WHEN lmp_usd_mwh <= {NEG_THRESHOLD} THEN 1 ELSE 0 END)
                       AS neg_share_pct
            FROM eim_prices GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
            """
        ).df()


def build(figures_dir=None):
    df = calendar_data()
    bas = sorted(df["ba_code"].unique())
    fig, axes = plt.subplots(1, len(bas), figsize=(10.5, 3.6), dpi=200, sharey=True)
    vmax = df["neg_share_pct"].max()
    for ax, ba in zip(np.atleast_1d(axes), bas, strict=True):
        sub = df[df["ba_code"] == ba].pivot(index="hour", columns="month",
                                            values="neg_share_pct")
        sub = sub.reindex(index=range(24), columns=range(1, 13))
        im = ax.imshow(sub, aspect="auto", origin="lower", cmap="Blues", vmin=0, vmax=vmax)
        ax.set_title(ba, fontsize=10, color=INK)
        ax.set_xticks(range(0, 12, 2), ["J", "M", "M", "J", "S", "N"])
        ax.set_yticks(range(0, 24, 6))
        ax.tick_params(colors=INK_2, length=0)
        ax.set_xlabel("Month", color=INK_2, fontsize=9)
    np.atleast_1d(axes)[0].set_ylabel("Hour of day (MST)", color=INK_2, fontsize=9)
    cbar = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02)
    cbar.set_label("Share of days with price ≤ $0 (%)", color=INK_2, fontsize=9)
    cbar.outline.set_visible(False)
    demo_banner(fig, pipeline_mode())
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
