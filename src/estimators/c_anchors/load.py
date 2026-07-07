"""Estimator C — documented curtailment anchors.

Loads the hand-curated anchors CSV (real filings; empty until Phase 3 mining
is done by the builder) and, in demo mode only, the synthetic demo anchors.
Anchors stay in their native units; only percent-of-available anchors are
plotted against A and B, and no unit conversion ever borrows numbers from
the other estimators (independence is the point).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.pipeline import pipeline_mode
from src.store import connect, write_table

ANCHORS_CSV = Path(__file__).parent / "anchors.csv"


def run() -> pd.DataFrame:
    real = pd.read_csv(ANCHORS_CSV)
    real["provenance"] = "documented"
    frames = [real]
    if pipeline_mode() == "demo":
        with connect(read_only=True) as con:
            demo = con.execute("SELECT * FROM demo_anchors").df()
        demo["provenance"] = "demo-synthetic"
        frames.append(demo)
    frames = [f for f in frames if not f.empty]
    anchors = pd.concat(frames, ignore_index=True)
    anchors["year"] = pd.to_datetime(anchors["period_start"]).dt.year
    write_table(anchors, "estimator_c_anchors")
    return anchors


if __name__ == "__main__":
    print(run().to_string(index=False))
