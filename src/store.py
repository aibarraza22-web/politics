"""DuckDB analytical store.

One file-backed database at data/c2c.duckdb holds every analytical table
(fleet inventory, hourly actuals, modeled potential, estimator outputs).
It is fully regenerable and gitignored; parquet files under data/ are the
durable cache, duckdb is the query layer.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.config import DUCKDB_PATH


def connect(db_path: Path | None = None, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(db_path) if db_path is not None else DUCKDB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def write_table(
    df: pd.DataFrame,
    table: str,
    db_path: Path | None = None,
) -> None:
    """Replace `table` with the contents of `df`."""
    with connect(db_path) as con:
        con.register("_incoming", df)
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM _incoming")


def read_table(table: str, db_path: Path | None = None) -> pd.DataFrame:
    with connect(db_path, read_only=True) as con:
        return con.execute(f"SELECT * FROM {table}").df()
