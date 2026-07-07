# Curtailment-to-Compute: Arizona

How much otherwise-wasted Arizona solar energy could power flexible AI compute, and what is it worth?

A quantified, reproducible answer, built as an open research codebase: (1) an hourly-resolution dataset of **estimated** Arizona solar curtailment, (2) a simulation of flexible compute scheduled into surplus windows, (3) an interactive explorer, and (4) a working paper with full replication code.

**Why "estimated":** unlike CAISO, Arizona's balancing authorities (APS, SRP, TEP) do not publish curtailment data. We triangulate three independent estimators — a calibrated physical potential-vs-actual model (pvlib), a WEIM negative-price market signal, and hand-curated documented anchors from regulatory filings — and we report the range, never a faked consensus. See [`SPEC.md`](SPEC.md) for the methodology and [`SOURCES.md`](SOURCES.md) for the data source log.

## Status: full pipeline built, running in DEMO mode

All five phases (fleet + actuals → potential model → estimators A/B/C → compute simulation → paper + explorer) are implemented and run end to end. **But:** the environment this was built in had no network route to EIA/NREL/CAISO, so the pipeline currently runs on a **synthetic validation fixture with known injected curtailment** (`src/demo_data.py`), and every real-data fetcher is `unverified-live` (checklist in `SOURCES.md`).

The fixture is used honestly, as a methods test: the estimators must recover curtailment we injected on purpose, through realistic obstacles (weather error, unobserved outages, imputed hours, measurement noise, inverter clipping). Estimator A's 5–95% band covers the injected truth in 8 of 9 BA-years — the coverage a 90% band should have. Every figure and page carries a SYNTHETIC banner until the pipeline runs on real data. **No output of this repo is currently an estimate of actual Arizona curtailment.**

## Reproduce

Prerequisites: [uv](https://docs.astral.sh/uv/) and [Quarto](https://quarto.org/docs/get-started/) (≥1.6; PDF via bundled Typst — no LaTeX).

```sh
make setup     # install pinned deps into .venv
make demo      # synthetic fixtures -> calibration -> estimators -> scenarios (~1 min, no keys)
make paper     # regenerate all figures + render paper to PDF and HTML
make test      # 18 tests incl. the ground-truth recovery test
open explorer/index.html   # interactive explorer (static, no server needed)
```

To run on real data (once fetchers are live-verified per `SOURCES.md`): put free EIA + NREL keys in `.env` (`cp .env.example .env`), then `make real && make paper`.

## Layout

```
data/{raw,interim,final}/       # regenerable; gitignored
src/config.py, src/store.py     # paths, .env keys, duckdb store
src/demo_data.py                # synthetic fixture generator w/ injected truth (DEMO ONLY)
src/pipeline.py                 # demo/real orchestration + 930-vs-923 reconciliation
src/fleet/                      # EIA-860/923/930 fetchers (real mode, unverified-live)
src/potential/                  # pvlib model + per-plant calibration + holdout validation
src/estimators/                 # a_potential_gap, b_eim_prices, c_anchors/
src/computeflex/                # scheduler + scenario grid + tornado sensitivity
src/figures/                    # one script = one figure_id; `make figures`
paper/                          # Quarto working paper (Typst PDF + HTML)
explorer/                       # static explorer (index.html + generated data.js)
tests/
```

## Honesty rules

Estimation under uncertainty; intellectual honesty is the product. Uncertainty bands on every estimate, holdout validation, no estimator averaging, explicit economic-vs-physical distinction, a pre-registered "ways this could be wrong" section (already written — see the paper), and all scenario assumptions in one visible table. Enforcement checklist: `CLAUDE.md` and `SPEC.md §7`.
