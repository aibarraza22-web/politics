"""figure_id: fig-seasonal-diurnal

Phase 1 exploratory: mean solar generation by month x hour-of-day per BA,
from the hourly BA series with imputed hours excluded. Sequential single-hue
colormap (magnitude), shared color scale across BAs.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from src.figures.style import INK_2, SEQUENTIAL_CMAP, demo_banner, save
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-seasonal-diurnal"


def build(figures_dir=None):
    with connect(read_only=True) as con:
        df = con.execute(
            """
            SELECT ba_code,
                   EXTRACT(month FROM ts_utc - INTERVAL 7 HOUR) AS month,
                   EXTRACT(hour  FROM ts_utc - INTERVAL 7 HOUR) AS hour,
                   AVG(solar_mw) AS mw
            FROM hourly_ba_solar
            WHERE NOT COALESCE(is_imputed, TRUE)
            GROUP BY 1, 2, 3
            """
        ).df()

    bas = sorted(df["ba_code"].unique())
    vmax = df["mw"].max()
    fig, axes = plt.subplots(1, len(bas), figsize=(10.5, 3.6), dpi=200, sharey=True)
    for ax, ba in zip(np.atleast_1d(axes), bas, strict=True):
        sub = df[df["ba_code"] == ba].pivot(index="hour", columns="month", values="mw")
        sub = sub.reindex(index=range(24), columns=range(1, 13))
        im = ax.imshow(
            sub, aspect="auto", origin="lower", cmap=SEQUENTIAL_CMAP, vmin=0, vmax=vmax
        )
        ax.set_title(ba, fontsize=10)
        ax.set_xticks(range(0, 12, 2), ["J", "M", "M", "J", "S", "N"])
        ax.set_yticks(range(0, 24, 6))
        ax.tick_params(colors=INK_2, length=0)
        ax.set_xlabel("Month", color=INK_2, fontsize=9)
    np.atleast_1d(axes)[0].set_ylabel("Hour of day (MST)", color=INK_2, fontsize=9)
    cbar = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02)
    cbar.set_label("Mean solar generation (MW)", color=INK_2, fontsize=9)
    cbar.outline.set_visible(False)
    demo_banner(fig, pipeline_mode())
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
