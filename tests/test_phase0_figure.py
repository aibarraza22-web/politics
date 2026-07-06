"""Sanity checks on the Phase 0 clear-sky figure pipeline.

These assert physics, not pixels: if the clear-sky model or the store
round-trip breaks, the numbers below move far outside their bounds.
"""

import duckdb

from src.figures.fig_phase0_clearsky import TABLE, build


def test_build_pipeline_and_physics(tmp_path):
    db = tmp_path / "test.duckdb"
    png = build(db_path=db, parquet_dir=tmp_path, figures_dir=tmp_path)

    assert png.exists() and png.stat().st_size > 10_000
    assert (tmp_path / f"{TABLE}.parquet").exists()

    with duckdb.connect(str(db), read_only=True) as con:
        df = con.execute(f"SELECT * FROM {TABLE}").df()

    june = df[df["day"] == "June 21"].set_index("hour_of_day")["ghi_wm2"]
    dec = df[df["day"] == "December 21"].set_index("hour_of_day")["ghi_wm2"]

    # Phoenix clear-sky solar noon GHI: ~1000 W/m2 in June, ~550 in December.
    assert 900 < june.max() < 1150
    assert 450 < dec.max() < 650
    assert june.max() > dec.max()

    # No irradiance at local midnight; none negative anywhere.
    assert june.loc[0.0] == 0 and dec.loc[0.0] == 0
    assert (df["ghi_wm2"] >= 0).all()

    # Day length: June daylight window is wider than December's.
    assert (june > 0).sum() > (dec > 0).sum()
