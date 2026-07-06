# Curtailment-to-Compute Arizona — all entry points.
# Requires: uv (https://docs.astral.sh/uv/) and quarto (https://quarto.org).

.PHONY: setup figures paper test lint clean

setup:
	uv sync

# Every paper figure regenerates from here. One script per figure in src/figures/.
figures:
	uv run python -m src.figures.fig_phase0_clearsky

paper: figures
	QUARTO_PYTHON=$(CURDIR)/.venv/bin/python quarto render paper

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

clean:
	rm -rf paper/_output paper/figures data/c2c.duckdb data/final/*.parquet
