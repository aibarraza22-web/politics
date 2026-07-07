"""Shared figure style: validated palette + paper-figure conventions.

Categorical slots are assigned in fixed order (never cycled); the BA slots
below are pinned so a BA keeps its hue across every figure in the paper.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

# Validated categorical palette, light mode (see dataviz validation in repo
# history): slots 1-4.
SERIES = ["#2a78d6", "#1baf7a", "#eda100", "#008300"]
BA_COLORS = {"AZPS": "#2a78d6", "SRP": "#1baf7a", "TEPC": "#eda100"}
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e0"
SPINE = "#c3c2b7"
SEQUENTIAL_CMAP = "Blues"  # single hue, light -> dark


def new_axes(figsize=(7.2, 4.2)):
    fig, ax = plt.subplots(figsize=figsize, dpi=200)
    style_axes(ax)
    return fig, ax


def style_axes(ax) -> None:
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(SPINE)
    ax.tick_params(colors=INK_2)


def demo_banner(fig, mode: str) -> None:
    """Stamp non-real data loudly. Called by every figure script."""
    if mode != "real":
        fig.text(
            0.5,
            0.995,
            "SYNTHETIC DEMONSTRATION DATA — not an estimate of actual Arizona curtailment",
            ha="center",
            va="top",
            fontsize=8,
            color="#8a1c1c",
            fontweight="bold",
        )


def save(fig, figure_id: str, figures_dir=None):
    from src.config import FIGURES_DIR

    out_dir = figures_dir or FIGURES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{figure_id}.png"
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out
