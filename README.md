# Curtailment-to-Compute: Arizona

How much otherwise-wasted Arizona solar energy could power flexible AI compute, and what is it worth?

A quantified, reproducible answer, built as an open research codebase: (1) an hourly-resolution dataset of **estimated** Arizona solar curtailment, (2) a simulation of flexible compute scheduled into surplus windows, (3) an interactive explorer, and (4) a working paper with full replication code.

**Why "estimated":** unlike CAISO, Arizona's balancing authorities (APS, SRP, TEP) do not publish curtailment data. We triangulate three independent estimators — a calibrated physical potential-vs-actual model (pvlib), a WEIM negative-price market signal, and hand-curated documented anchors from regulatory filings — and we report the range, never a faked consensus. See [`SPEC.md`](SPEC.md) for the methodology and [`SOURCES.md`](SOURCES.md) for the data source log.

## Status: running on REAL data (with stated substitutions)

All five phases run end to end on live data: EIA-930 bulk hourly series (imputation flags handled, physically impossible hours excluded), the EIA-860 2024 fleet (89 plants / ~3.09 GW across the three AZ BAs), EIA-923 monthly calibration, CAISO OASIS WEIM 5-minute prices at the Arizona EIM LAPs (Apr 2023+, the full published history), and verbatim-verified documented anchors. Every fetcher was verified against live responses — see the war stories in `SOURCES.md`.

Headline real-data findings so far (see the paper for the careful version):

- **AZPS's EIA-930 solar series cannot be attributed to its utility-scale fleet** (40–74% excess vs. all plant-level generation; its 2024 series implies an impossible ~37% fleet capacity factor). Estimator A is therefore published for SRP and TEPC only — a finding, not a workaround.
- **The WEIM negative-price signal is large and growing**: negative-price daylight hours roughly doubled from 2023 to 2024 (SRP 8.8%→21.0%, TEPC 10.2%→18.7%, AZPS 15.8%→25.6%), vs. a documented 2.9%-of-potential APS curtailment rate in 2018.
- Estimator A's bands on real data are wide (medians mostly ≈0, upper bounds 6–28%): the ERA5-blend weather stand-in is the limiting factor. **The NSRDB re-run is the top robustness check owed** (`developer.nrel.gov` was unreachable from this build environment).

The synthetic fixture (`make demo`) remains as the method-validation harness: Estimator A's band covered known injected truth in 8 of 9 BA-years before it ever touched real data.

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
