# Curtailment-to-Compute Arizona — all entry points.
# Requires: uv (https://docs.astral.sh/uv/) and quarto (https://quarto.org).

.PHONY: setup demo real figures paper test lint clean

setup:
	uv sync

# Full demo pipeline: synthetic fixtures with injected ground truth ->
# calibration -> estimators -> compute scenarios -> explorer data.
# This is the only mode that runs without network access + API keys.
demo:
	uv run python -m src.pipeline --mode demo
	uv run python -m src.potential.calibrate
	uv run python -m src.estimators.a_potential_gap
	uv run python -m src.estimators.b_eim_prices
	uv run python -m src.estimators.c_anchors.load
	uv run python -m src.computeflex.scenarios
	uv run python -m src.value
	uv run python -m src.explorer_export

# Real mode: needs EIA_API_KEY in .env and network access. All fetchers are
# live-verified (see SOURCES.md); weather prefers the NSRDB S3 mirror.
real:
	uv run python -m src.pipeline --mode real
	uv run python -m src.potential.calibrate
	uv run python -m src.estimators.a_potential_gap
	uv run python -m src.estimators.b_eim_prices
	uv run python -m src.estimators.c_anchors.load
	uv run python -m src.computeflex.scenarios
	uv run python -m src.value
	uv run python -m src.explorer_export

# Every paper figure regenerates from the duckdb store (build it first via
# `make demo` or `make real`). One script per figure in src/figures/.
figures:
	uv run python -m src.figures.fig_phase0_clearsky
	uv run python -m src.figures.fig_seasonal_diurnal
	uv run python -m src.figures.fig_potential_validation
	uv run python -m src.figures.fig_estimator_triangulation
	uv run python -m src.figures.fig_negative_price_hours
	uv run python -m src.figures.fig_neg_price_calendar
	uv run python -m src.figures.fig_tradeoff_curve
	uv run python -m src.figures.fig_tornado

paper: figures
	QUARTO_PYTHON=$(CURDIR)/.venv/bin/python quarto render paper

test:
	uv run pytest -q

lint:
	uv run ruff check src tests

clean:
	rm -rf paper/_output paper/figures data/c2c.duckdb data/final/*.parquet \
	  data/interim/demo explorer/data.js
