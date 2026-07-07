"""figure_id: fig-tornado

One-at-a-time sensitivity of the reference scenario's surplus share.
Diverging bars around the base value; parameters sorted by impact.
"""

from __future__ import annotations

import numpy as np

from src.figures.style import INK, INK_2, SERIES, demo_banner, save, style_axes
from src.pipeline import pipeline_mode
from src.store import connect

FIGURE_ID = "fig-tornado"


def build(figures_dir=None):
    import matplotlib.pyplot as plt

    with connect(read_only=True) as con:
        t = con.execute("SELECT * FROM computeflex_tornado").df()
    t["span"] = t["high"] - t["low"]
    t = t.sort_values("span").reset_index(drop=True)
    base = 100 * t["base"].iat[0]

    fig, ax = plt.subplots(figsize=(7.6, 3.8), dpi=200)
    style_axes(ax)
    y = np.arange(len(t))
    ax.barh(y, 100 * t["high"] - base, left=base, height=0.55, color=SERIES[0])
    ax.barh(y, 100 * t["low"] - base, left=base, height=0.55, color=SERIES[2])
    ax.axvline(base, color=INK, linewidth=1)
    ax.set_yticks(y, t["parameter"], fontsize=9)
    ax.set_xlabel(
        "Surplus share of DC energy (%) — reference scenario, one-at-a-time", color=INK_2
    )
    for yi, row in t.iterrows():
        ax.text(100 * row["high"] + 0.3, yi, f"{100 * row['high']:.1f}", va="center",
                fontsize=8, color=INK)
        ax.text(100 * row["low"] - 0.3, yi, f"{100 * row['low']:.1f}", va="center",
                ha="right", fontsize=8, color=INK)
    ax.grid(axis="x", color="#e6e5e0", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, max(32, 100 * t["high"].max() + 5))
    fig.tight_layout()
    demo_banner(fig, pipeline_mode())
    return save(fig, FIGURE_ID, figures_dir)


if __name__ == "__main__":
    print(build())
