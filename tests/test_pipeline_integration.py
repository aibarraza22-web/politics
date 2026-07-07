"""Integration checks against the built demo pipeline (data/c2c.duckdb).

These validate the honesty-critical properties end to end:
- reconciliation within documented tolerance,
- Estimator A's 5-95% band contains the injected truth (the recovery test),
- imputed hours are excluded from reconciliation sums.

They skip (not pass) when the store hasn't been built — CI builds it first
via `make demo`.
"""

import duckdb
import pytest

from src.config import DUCKDB_PATH


def con():
    if not DUCKDB_PATH.exists():
        pytest.skip("demo pipeline not built (run `make demo`)")
    c = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    tables = {r[0] for r in c.execute("SHOW TABLES").fetchall()}
    if "estimator_a_annual" not in tables:
        pytest.skip("estimators not run yet (run `make demo`)")
    return c


def test_mode_is_labeled():
    mode = con().execute("SELECT mode FROM pipeline_meta").fetchone()[0]
    assert mode in ("demo", "real")


def test_reconciliation_within_tolerance():
    rec = con().execute("SELECT * FROM reconciliation").df()
    assert len(rec) > 0
    assert rec["within_tolerance"].all()


def test_estimator_a_band_contains_injected_truth():
    c = con()
    if c.execute("SELECT mode FROM pipeline_meta").fetchone()[0] != "demo":
        pytest.skip("recovery test only applies in demo mode")
    df = c.execute(
        """
        WITH truth AS (
            SELECT ba_code, EXTRACT(year FROM ts_utc - INTERVAL 7 HOUR) AS year,
                   100 * SUM(true_curtailment_mwh) / SUM(true_available_mwh) AS true_pct
            FROM demo_truth_ba_hour GROUP BY 1, 2 HAVING SUM(true_available_mwh) > 1000
        )
        SELECT a.ba_code, a.year, a.curt_lo_pct, a.curt_hi_pct, t.true_pct
        FROM estimator_a_annual a JOIN truth t USING (ba_code, year)
        """
    ).df()
    assert len(df) >= 9
    inside = (df["true_pct"] >= df["curt_lo_pct"]) & (df["true_pct"] <= df["curt_hi_pct"])
    # A 5-95% band claims ~90% coverage, not 100%: with 9 BA-years, expect
    # ~8 inside. (Observed miss: a heavy unobserved-outage year read as
    # curtailment — the confounder the band is honest about.)
    assert inside.mean() >= 8 / 9, f"band coverage too low:\n{df[~inside]}"


def test_estimator_b_is_an_upper_bound_on_economic_truth():
    c = con()
    if c.execute("SELECT mode FROM pipeline_meta").fetchone()[0] != "demo":
        pytest.skip("demo mode only")
    df = c.execute(
        """
        WITH truth AS (
            SELECT ba_code, EXTRACT(year FROM ts_utc - INTERVAL 7 HOUR) AS year,
                   SUM(CASE WHEN curtailment_type = 'economic'
                       THEN true_curtailment_mwh ELSE 0 END) AS econ_mwh
            FROM demo_truth_ba_hour GROUP BY 1, 2 HAVING SUM(true_available_mwh) > 1000
        )
        SELECT b.upper_bound_mwh, t.econ_mwh FROM estimator_b_annual b
        JOIN truth t USING (ba_code, year)
        """
    ).df()
    assert (df["upper_bound_mwh"] >= df["econ_mwh"]).all()


def test_no_imputed_hours_in_estimator_a_hourly():
    c = con()
    df = c.execute(
        """
        SELECT COUNT(*) AS n FROM estimator_a_hourly a
        JOIN hourly_ba_solar h USING (ba_code, ts_utc)
        WHERE h.is_imputed AND a.curt_mid IS NOT NULL
        """
    ).df()
    assert df["n"].iat[0] == 0
