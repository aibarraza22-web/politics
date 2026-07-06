# Curtailment-to-Compute: Arizona

How much otherwise-wasted Arizona solar energy could power flexible AI compute, and what is it worth?

A quantified, reproducible answer, built as an open research codebase. Deliverables: (1) an open hourly-resolution dataset of **estimated** Arizona solar curtailment, (2) a simulation of flexible compute scheduled into curtailment/surplus windows, (3) an interactive explorer, and (4) a working paper with full replication code.

**Why "estimated":** unlike CAISO, Arizona's balancing authorities (APS, SRP, TEP) do not publish curtailment data. We triangulate three independent estimators — a physical potential-vs-actual model (pvlib + NSRDB + EIA data), a WEIM negative-price market signal, and hand-curated documented anchors from regulatory filings — and we report the range, never a faked consensus. See [`SPEC.md`](SPEC.md) for the full methodology and [`SOURCES.md`](SOURCES.md) for the data source log.

## Status

**Phase 0 — Scaffold: complete.** Repo, CI, `.env` key wiring, duckdb store, and a Quarto paper stub that renders PDF + HTML with one data-driven figure (pvlib clear-sky curves for Phoenix — real physics, no API key needed). Phases 1–5 (fleet + actuals → potential model → estimators → compute simulation → paper + explorer) are specified in `SPEC.md §6`.

## Reproduce

Prerequisites: [uv](https://docs.astral.sh/uv/) and [Quarto](https://quarto.org/docs/get-started/) (≥1.4; PDF output uses Quarto's bundled Typst — no LaTeX needed).

```sh
make setup                # install pinned Python deps into .venv
cp .env.example .env      # then add your two free API keys (EIA, NREL)
                          # (not needed for Phase 0 — the stub figure is key-free)
make paper                # regenerate figures + render paper to PDF and HTML
make test                 # pytest
```

Outputs land in `paper/_output/` (paper.pdf, paper.html) and `paper/figures/`.

## Layout

```
data/{raw,interim,final}/   # regenerable; raw API pulls cached as parquet (gitignored)
src/config.py               # repo paths + .env key loading
src/store.py                # duckdb analytical store (data/c2c.duckdb)
src/fleet/                  # EIA-860/923 fleet builder + calibration        (Phase 1)
src/potential/              # NSRDB + pvlib modeled potential output         (Phase 2)
src/estimators/             # a_potential_gap, b_eim_prices, c_anchors/      (Phase 3)
src/computeflex/            # flexible-compute scheduling simulation         (Phase 4)
src/figures/                # one script = one figure_id; all via `make figures`
paper/                      # Quarto working paper (PDF via Typst + HTML)
explorer/                   # static interactive explorer                    (Phase 5)
tests/
```

## Honesty rules

This analysis is estimation under uncertainty, and intellectual honesty is the product: uncertainty bands on every estimate, holdout validation for the physical model, no estimator averaging, and an explicit economic-vs-physical curtailment distinction. The enforcement checklist lives in `CLAUDE.md` and `SPEC.md §7`.
