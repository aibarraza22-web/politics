import pandas as pd

from src.store import read_table, write_table


def test_write_and_read_roundtrip(tmp_path):
    db = tmp_path / "test.duckdb"
    df = pd.DataFrame({"ba": ["AZPS", "SRP", "TEPC"], "mwh": [1.5, 2.0, 0.0]})
    write_table(df, "roundtrip", db_path=db)
    out = read_table("roundtrip", db_path=db)
    pd.testing.assert_frame_equal(out, df)


def test_write_table_replaces(tmp_path):
    db = tmp_path / "test.duckdb"
    write_table(pd.DataFrame({"x": [1, 2, 3]}), "t", db_path=db)
    write_table(pd.DataFrame({"x": [9]}), "t", db_path=db)
    assert read_table("t", db_path=db)["x"].tolist() == [9]
