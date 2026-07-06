"""figure_id: fig-phase0-clearsky

Phase 0 pipeline proof: clear-sky global horizontal irradiance for Phoenix on
the June and December solstices, from pvlib's Ineichen model. No API key is
needed — this exercises the full data path (compute -> parquet -> duckdb ->
figure) before any external source is wired in. Linke turbidity is fixed at 3
rather than looked up from the climatology table, so the curves are a clean
physical illustration, not a fleet-potential estimate.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd
from pvlib.location import Location

from src.config import DUCKDB_PATH, FIGURES_DIR, FINAL_DIR
from src.store import connect, write_table

FIGURE_ID = "fig-phase0-clearsky"
TABLE = "phase0_clearsky"

# Phoenix Sky Harbor
PHOENIX = Location(latitude=33.4484, longitude=-112.0740, tz="America/Phoenix", altitude=331)
DAYS = {"June 21": "2025-06-21", "December 21": "2025-12-21"}
LINKE_TURBIDITY = 3.0

# Validated categorical slots 1-2 (light mode); identity is also carried by
# direct labels, so the palette's low-contrast aqua is legal here.
SERIES_COLORS = {"June 21": "#2a78d6", "December 21": "#1baf7a"}
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"


def build_dataset() -> pd.DataFrame:
    frames = []
    for label, date in DAYS.items():
        times = pd.date_range(
            f"{date} 00:00", f"{date} 23:55", freq="5min", tz=PHOENIX.tz
        )
        cs = PHOENIX.get_clearsky(times, model="ineichen", linke_turbidity=LINKE_TURBIDITY)
        frames.append(
            pd.DataFrame(
                {
                    "day": label,
                    "timestamp": times.tz_localize(None),
                    "hour_of_day": times.hour + times.minute / 60,
                    "ghi_wm2": cs["ghi"].to_numpy(),
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def build(
    db_path: Path | None = None,
    parquet_dir: Path | None = None,
    figures_dir: Path | None = None,
) -> Path:
    """Compute the dataset, persist it (parquet + duckdb), plot from duckdb.

    Returns the path of the rendered PNG.
    """
    db_path = db_path or DUCKDB_PATH
    parquet_dir = parquet_dir or FINAL_DIR
    figures_dir = figures_dir or FIGURES_DIR
    parquet_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    df = build_dataset()
    df.to_parquet(parquet_dir / f"{TABLE}.parquet", index=False)
    write_table(df, TABLE, db_path=db_path)

    # Plot from the store, not the in-memory frame: the figure provably
    # regenerates from persisted data.
    with connect(db_path, read_only=True) as con:
        plot_df = con.execute(
            f"SELECT day, hour_of_day, ghi_wm2 FROM {TABLE} ORDER BY day, hour_of_day"
        ).df()

    fig, ax = plt.subplots(figsize=(7.2, 4.2), dpi=200)
    for label in DAYS:
        sub = plot_df[plot_df["day"] == label]
        ax.plot(sub["hour_of_day"], sub["ghi_wm2"], color=SERIES_COLORS[label], linewidth=2)
        peak = sub.loc[sub["ghi_wm2"].idxmax()]
        ax.annotate(
            f"{label}\npeak {peak.ghi_wm2:.0f} W/m²",
            xy=(peak.hour_of_day, peak.ghi_wm2),
            xytext=(peak.hour_of_day, peak.ghi_wm2 + 40),
            ha="center",
            fontsize=9,
            color=INK,
        )

    ax.set_xlim(0, 24)
    ax.set_ylim(0, 1250)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Hour of day (America/Phoenix)", color=INK_SECONDARY)
    ax.set_ylabel("Clear-sky GHI (W/m²)", color=INK_SECONDARY)
    ax.grid(axis="y", color="#e6e5e0", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#c3c2b7")
    ax.tick_params(colors=INK_SECONDARY)

    fig.tight_layout()
    out = figures_dir / f"{FIGURE_ID}.png"
    fig.savefig(out)
    plt.close(fig)
    return out


if __name__ == "__main__":
    print(build())
