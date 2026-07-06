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

## Current phase: Phase 0 — Scaffold ✅ → Phase 1 — Fleet + actuals

**Phase 0 acceptance (met):** repo + CI, API keys (EIA, NREL) wired via `.env`, duckdb store, Quarto rendering; `make paper` renders a stub PDF with one data-driven figure.

**Phase 1 acceptance (next):** AZ solar fleet table built from EIA-860; EIA-930 hourly pulled for AZPS/SRP/TEPC with imputation flags handled; EIA-923 monthly per plant; exploratory notebook on seasonal/diurnal patterns per BA. Done when: validated hourly dataset covering ≥3 years, and the fleet table reconciles with 930 aggregate solar within a documented tolerance.

## Working conventions

- Python ≥3.11 (spec targets 3.12), managed with `uv`; run everything through `uv run` or `make` targets.
- Analytical store: duckdb at `data/c2c.duckdb` (gitignored, fully regenerable). Raw pulls cached to parquet under `data/raw/`.
- Every paper figure = one script in `src/figures/` with a unique `figure_id`; output lands in `paper/figures/`. Every quantitative sentence in the paper must trace to a `figure_id` or `table_id`.
- Log every data source in `SOURCES.md` with retrieval date and verification status before building parsers against it.
- Escalate (don't silently proceed) if: EIA-930 solar for a BA is too noisy/imputed to support Estimator A, or CAISO OASIS EIM access differs materially from the spec's assumptions.

## Commands

- `make setup` — install deps (uv sync)
- `make figures` — regenerate every figure from data
- `make paper` — figures + render the Quarto paper (PDF via typst + HTML)
- `make test` / `make lint` — pytest / ruff
