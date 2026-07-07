# CLAUDE.md — Curtailment-to-Compute Arizona

This is research code: correctness beats elegance, and honesty beats impressiveness. Never smooth over estimator disagreement. Every figure regenerates from `make figures`. Inspect real API responses before writing parsers. When a result looks surprisingly good, treat it as a bug until proven otherwise.

Full project spec: `SPEC.md`. Data source log: `SOURCES.md`.

## The core methodological problem

Arizona utilities (APS, SRP, TEP — BA codes AZPS, SRP, TEPC in EIA-930) do **not** publish curtailment data. Curtailment must therefore be **estimated**, and the estimation strategy is the paper's core methods contribution. Three independent estimators, triangulated — never averaged:

- **A — Potential-vs-actual:** pvlib physical model of the AZ utility-scale fleet (EIA-860 inventory + NSRDB irradiance), calibrated per plant on clearly-unconstrained months. Curtailment proxy = modeled potential − reported actual (EIA-930 hourly; EIA-923 monthly for calibration). Confounders (weather-model error, outages, derates) handled via calibration-period residual distributions with reported uncertainty bands.
- **B — Market-signal:** CAISO OASIS WEIM locational prices at Arizona nodes; frequency and depth of zero/negative-price hours = economic-curtailment signal. Verify actual OASIS report names and node naming before building anything — do not trust the spec.
- **C — Documented anchors:** hand-curated CSV of curtailment statements from IRPs, ACC/FERC filings, investor materials. Every row has a source URL and quote.

If A, B, and C disagree wildly, that is a publishable finding ("Arizona has no idea how much solar it wastes"). **Never average estimators to fake convergence; present the range.**

## Statistical honesty rules (enforced in review)

- Uncertainty bands on every estimate.
- Holdout validation for the potential model (held-out months, per-plant MAE reported).
- No estimator averaging, ever.
- Distinguish **economic** curtailment (priced out) from **physical** curtailment (grid-constrained); our methods mostly see the union and must say so explicitly.
- A "ways this could be wrong" section is written **before** results are final (pre-registered skepticism).
- All scenario assumptions live in one visible table.
- EIA-930 imputed hours are flagged upstream — exclude or handle explicitly, never silently ingest.

## Current phase: Phases 0–5 built in DEMO MODE → live-data verification

All five phases exist and run end to end (`make demo && make paper && make test`), but **on a synthetic validation fixture with injected ground-truth curtailment** — this build environment had no network route to EIA/NREL/CAISO, so every real-mode fetcher is `unverified-live`. The fixture is a recovery test (estimators must find the injected truth within their bands; A covers 8/9 BA-years), never a source of Arizona claims. Every figure carries a SYNTHETIC banner unless `pipeline_meta.mode = 'real'`.

**Next milestone:** on a networked machine, work through the live-verification checklist in `SOURCES.md` (inspect raw responses, fix parsers, wire NSRDB, investigate OASIS report/node names), then `make real` and re-validate: reconciliation within tolerance, holdout MAE acceptable, triangulation figure regenerated with real divergence discussed — never averaged.

## Working conventions

- Python ≥3.11 (spec targets 3.12), managed with `uv`; run everything through `uv run` or `make` targets.
- Analytical store: duckdb at `data/c2c.duckdb` (gitignored, fully regenerable). Raw pulls cached to parquet under `data/raw/`.
- Every paper figure = one script in `src/figures/` with a unique `figure_id`; output lands in `paper/figures/`. Every quantitative sentence in the paper must trace to a `figure_id` or `table_id`.
- Log every data source in `SOURCES.md` with retrieval date and verification status before building parsers against it.
- Escalate (don't silently proceed) if: EIA-930 solar for a BA is too noisy/imputed to support Estimator A, or CAISO OASIS EIM access differs materially from the spec's assumptions.

## Commands

- `make setup` — install deps (uv sync)
- `make demo` — full pipeline on the synthetic fixture (no keys/network needed)
- `make real` — full pipeline on live data (needs `.env` keys + verified fetchers)
- `make figures` — regenerate every figure from the duckdb store
- `make paper` — figures + render the Quarto paper (PDF via typst + HTML)
- `make test` / `make lint` — pytest / ruff
