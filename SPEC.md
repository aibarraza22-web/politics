# SPEC — Project 3: Curtailment-to-Compute Arizona (research codebase + working paper)

## 1. Mission and context

You are building the research codebase for Curtailment-to-Compute: a quantified, reproducible answer to the question "How much otherwise-wasted Arizona solar energy could power flexible AI compute, and what is it worth?" Deliverables: (1) an open dataset of estimated Arizona solar curtailment at hourly resolution, (2) a simulation of flexible compute scheduled into curtailment/surplus windows, (3) an interactive explorer page, and (4) a working-paper-quality writeup with full replication code. Solo developer-researcher; the paper and repo are the career artifact (think arXiv/SSRN preprint + a Works-in-Progress-style essay).

Intellectual honesty is the product. This analysis involves estimation under uncertainty. Every result ships with sensitivity analysis. Overclaiming destroys the entire value of the project.

## 2. The central methodological problem (read carefully — this shapes everything)

Unlike CAISO, Arizona utilities do not publish curtailment data. APS, SRP, and TEP are their own balancing authorities (BA codes AZPS, SRP, TEPC in EIA-930) and report hourly demand, net generation by fuel, and interchange — but not curtailed MWh. Therefore curtailment must be estimated, and the estimation strategy is the paper's core methods contribution. Build three independent estimators and triangulate:

* **Estimator A — Potential-vs-actual:** Model expected solar output for Arizona's utility-scale fleet using EIA-860 plant inventory (location, capacity, tracking type) + NREL NSRDB irradiance data + pvlib physical modeling, calibrated per-plant against months where output is clearly unconstrained. Curtailment proxy = modeled potential − reported actual (EIA-930 hourly solar generation per BA; EIA-923 monthly per plant for calibration). Biggest confounders: weather-model error, outages, derates — handle via calibration-period residual distributions and report uncertainty bands.
* **Estimator B — Market-signal:** Arizona utilities participate in the Western Energy Imbalance Market (EIM/WEIM, operated by CAISO). CAISO OASIS publishes EIM locational prices. Hours with zero/negative prices at Arizona load-aggregation points indicate surplus conditions; frequency and depth of negative-price hours = economic-curtailment signal. Verify current data availability and node naming on CAISO OASIS before building — do not trust this spec.
* **Estimator C — Documented anchors:** Mine utility IRPs (APS/TEP Integrated Resource Plans), ACC filings, FERC filings, and investor materials for any stated curtailment figures or curtailment assumptions; use as ground-truth anchors to sanity-check A and B. Hand-curated CSV, every row with a source URL and quote.

If A, B, and C disagree wildly, that finding is publishable in itself — "Arizona has no idea how much solar it wastes" is a legitimate result. Never average estimators to fake convergence; present the range.

## 3. The compute model

Model a configurable flexible data center: parameters = IT capacity (MW), PUE, flexibility class (fully deferrable batch training / partially deferrable / firm), minimum-run constraints, checkpoint overhead cost for interruption, optional co-located battery (capacity, power, efficiency). Scheduling simulation: given hourly surplus/curtailment series, schedule workloads to maximize surplus-energy absorption subject to a job-completion SLA (e.g., X GPU-hours per week). Compute, per scenario: % of load served by otherwise-curtailed energy, effective energy cost vs. flat tariff, capacity factor achieved, and the tradeoff curve (utilization vs. surplus-share — the paper's headline figure). Include a skeptical scenario set: what flexibility level is actually realistic for frontier training (checkpointing costs, interconnect utilization economics) — cite the emerging literature on grid-flexible data centers and engage its critics; do not assume perfect flexibility.

## 4. Data sources (verify all live before coding; log in SOURCES.md with retrieval dates)

* EIA-930 hourly: demand, net generation by fuel, interchange for AZPS, SRP, TEPC (+ WALC context). EIA v2 API, free key. Backfill max history; note the known 930 data-quality issues (imputed hours are flagged — exclude or handle explicitly).
* EIA-860 / 860M: every AZ utility-scale solar plant — lat/lon, AC/DC capacity, tracking, in-service date.
* EIA-923: monthly per-plant generation for calibration.
* NREL NSRDB (PSM v3+): hourly irradiance/temperature at plant locations, via NREL developer API (free key, rate-limited — cache aggressively).
* pvlib-python: physical PV modeling.
* CAISO OASIS: WEIM prices (investigate the correct report + AZ nodes; document findings in SOURCES.md).
* Utility IRPs + ACC eDocket: curtailment statements (manual curation).
* Context for the writeup: LBNL data center energy report (2024), EIA/LBNL curtailment literature for CAISO/ERCOT as methodological precedent.

## 5. Architecture

Python 3.12; polars or pandas; duckdb for the analytical store; pvlib; matplotlib/plotnine for paper figures + a small static Observable/ECharts explorer page; Quarto for the paper (renders to PDF + HTML from the same source, executes code — guarantees figures match data). No cloud infra; everything runs on a laptop; NSRDB pulls cached to parquet.

```
/data/{raw,interim,final}/
/src/fleet/        # 860/923 fleet builder + calibration
/src/potential/    # NSRDB + pvlib modeled output
/src/estimators/   # a_potential_gap.py, b_eim_prices.py, c_anchors/
/src/computeflex/  # scheduling simulation
/src/figures/      # every paper figure = one script, one figure_id
/paper/            # Quarto working paper
/explorer/         # static interactive page
/tests/  SPEC.md CLAUDE.md SOURCES.md
```

## 6. Phases

**Phase 0 — Scaffold (day 1–2).** Repo, CI, API keys (EIA, NREL) wired via .env, duckdb store, Quarto hello-world rendering. Accept: `make paper` renders a stub PDF with one data-driven figure.

**Phase 1 — Fleet + actuals (week 1–2).** Build the AZ solar fleet table from 860; pull EIA-930 hourly for the three BAs with the imputation flags handled; pull 923 monthly per plant. Exploratory notebook: seasonal/diurnal solar patterns per BA. Accept: validated hourly dataset, ≥3 years; fleet table reconciles with 930 aggregate solar within a documented tolerance.

**Phase 2 — Potential model (week 2–4).** NSRDB pulls per plant; pvlib model per plant (tracking-aware); calibrate each plant on clearly-unconstrained periods; validate: modeled vs. actual on held-out months, report per-plant MAE. Accept: fleet-wide modeled generation within a stated error band on holdout periods, per-plant diagnostics saved.

**Phase 3 — Estimators A + B (week 4–6).** A: hourly gap series with uncertainty bands (propagate calibration residuals). B: EIM negative/zero-price hour analysis for AZ nodes. C: anchor CSV from IRP/docket mining. Triangulation notebook comparing all three by season and year. Accept: the three-estimator comparison figure exists with honest divergence discussion drafted.

**Phase 4 — Compute simulation (week 6–8).** The scheduler + scenario grid (flexibility classes × DC sizes × battery options × SLA levels); headline tradeoff curves; sensitivity analysis (tornado chart over key assumptions). Accept: full scenario grid runs in <30 min; results tables auto-generated into the paper.

**Phase 5 — Paper + explorer (week 8–12).** Working paper in Quarto: methods, results, limitations (a real limitations section — enumerate every confounder), policy implications kept modest and separate from findings. Explorer page: pick a year, see the surplus windows and what a hypothetical flexible DC would have absorbed. LLM assistance rules for the paper: Claude may draft prose from the builder's bullet outlines and check claims against the data tables; every quantitative sentence must trace to a figure_id or table_id; builder reviews everything. Accept: PDF + HTML paper fully reproducible via `make paper`; explorer deployed; replication README tested by a clean-machine run.

## 7. Statistical honesty requirements (enforce in review)

Uncertainty bands on every estimate; holdout validation for the potential model; no estimator averaging; explicit distinction between economic curtailment (priced out) and physical curtailment (grid-constrained) — our methods mostly see the union and must say so; a "ways this could be wrong" section written before results are final (pre-registered skepticism); all scenario assumptions in one visible table.

## 8. Definition of done for the grant demo

Public repo + rendered working paper + live explorer, where the abstract states a defensible range (not a point estimate) for annual Arizona solar surplus energy and the share of a flexible data center's load it could serve under stated assumptions — reproducible end-to-end by a stranger with two free API keys.

## 9. Escalation rules

If EIA-930 solar data for a BA proves too noisy/imputed to support Estimator A, escalate to the builder with evidence and options (e.g., restrict to APS, or lean on B+C) rather than silently proceeding. Same if CAISO OASIS access for EIM nodes turns out materially different than assumed.

## 10. CLAUDE.md contents to generate

Condense Sections 2, 7, and current-phase acceptance criteria. Include: "This is research code: correctness beats elegance, and honesty beats impressiveness. Never smooth over estimator disagreement. Every figure regenerates from `make figures`. Inspect real API responses before writing parsers. When a result looks surprisingly good, treat it as a bug until proven otherwise."
