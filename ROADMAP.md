# Roadmap: from Arizona case study to a flagship research project

The honest inventory of what exists, what it's worth, and the highest-leverage
path to making it matter — for admissions committees, for the research
community, and for the grid.

## What makes this project distinctive (already true)

1. **A real discovery**: AZPS, Arizona's largest utility, publishes an hourly
   solar series that cannot be attributed to its utility-scale fleet
   (40–74% excess, growing; `docs/eia930-azps-discrepancy.md`). Nobody else
   has published this.
2. **A real trend**: negative-price daylight hours at Arizona's EIM nodes
   roughly doubled 2023→2024 (SRP 8.8→21.0%, TEPC 10.2→18.7%, AZPS
   15.8→25.6%) — measured from CAISO's own 5-minute prices, full published
   history.
3. **A validated method**: the estimator machinery was proven on synthetic
   ground truth (8/9 band coverage) *before* touching real data — a
   methods-validation discipline most published curtailment studies skip.
4. **Radical reproducibility**: `make real` rebuilds everything from public
   APIs; every figure regenerates from the store; every schema surprise is
   logged in SOURCES.md.

## The leveled-up thesis

> **"The West is beginning to waste solar at scale, the public data for
> measuring it is broken in specific documented ways, and flexible compute
> is a candidate buyer of last resort — here is the first open, validated,
> multi-state measurement of all three claims."**

## Execution tracks (ordered by leverage)

### Track 1 — The Southwest Curtailment Atlas (highest impact-per-hour)
Extend Estimator B (and A where fleets reconcile) from 3 BAs to the whole
Western EIM. **Feasibility already verified live (2026-07-07):** OASIS
serves ELAP price data for `ELAP_{NEVP,PNM,EPE,PACE,IPCO,PSEI,BANC}-APND`
(probed; LADWP absent). The fetchers are BA-agnostic — expansion is a node
map + fleet filter, not new code. Deliverable: the first public
negative-price / surplus-signal dataset covering every non-transparent
Western BA, with per-BA reconciliation audits (expect more AZPS-style
findings — each one is a result).

### Track 2 — File and publish the data-integrity finding
Send `docs/eia930-azps-discrepancy.md` to EIA's Grid Monitor team and APS;
publish a short public writeup regardless of response. If EIA corrects or
explains the series, the project has demonstrably improved a federal
dataset. (This is the artifact that says "this person's work has already
been treated as authoritative" — the strongest possible signal.)

### Track 3 — NSRDB robustness re-run (in progress)
The ERA5→NSRDB weather swap, unblocked via the AWS Open Data S3 mirror
(surgical chunk reads of the 4km/30-min product; `src/potential/nsrdb_s3.py`).
Report the sensitivity of Estimator A's bands to weather source — the
pre-registered top robustness check.

### Track 4 — The paper, aimed properly
Target: arXiv preprint + a venue where energy-data work lands (Environmental
Research Letters, Joule commentary, or IAEE/USAEE student track). The
narrative order that works: (1) measurement is broken, (2) the surplus
signal is exploding anyway, (3) here's the validated range, (4) here's what
flexible compute could absorb, skeptically. Recruit one domain reviewer
(an NREL/LBNL curtailment author — O'Shaughnessy's group is the natural
fit and this work extends their 2021 study's Arizona thread).

### Track 5 — Make the explorer the front door
One page, all WEIM BAs, the negative-price trend animated year over year,
the AZPS finding as a callout. Journalists and admissions readers click
links; they do not clone repos.

### Track 6 — Anchor curation sprint (human work)
APS 2023 IRP, TEP 2023 IRP, SRP ISP, ACC eDocket search for "curtailment"
— target 5+ verified anchors in `anchors.csv`. Each anchor is a citation
the estimators can be graded against.

## Track 7 — Applications layer (BUILT 2026-07-07)

The importance ceiling isn't the estimate — it's whether specific actors can
act on it. Shipped:

- **The "when to run" calendar** (`fig-neg-price-calendar` + interactive in
  the explorer): month × hour share of negative-price days per BA. In
  March–May, 80–90% of midday days clear ≤ $0 — the operational window for
  any flexible load (compute, EV fleets, water, hydrogen, pre-cooling).
- **The value layer** (`src/value.py` → `value_annual`): banded avoided-cost
  dollars, AZ-homes equivalents, tCO₂ of displaced marginal gas, and an
  hourly-coincident estimate of producer payments during negative hours.
- **The living monitor** (`src/monitor_daily.py` +
  `.github/workflows/monitor.yml`): a keyless daily GitHub Action that pulls
  yesterday's OASIS prices and refreshes the explorer — the page is current
  every morning without anyone touching it. (Activates when merged to the
  default branch.)
- **Explorer v2**: retitled *Arizona Solar Waste Monitor*; value tiles,
  interactive calendar with hover, yesterday-on-the-grid strip.

Natural next applications (not yet built): a "flexible-load siting memo"
per utility (which BA, which months, what a PPA-plus-curtailment-rider
should pay); an SRP/TEP-specific one-pager for their IRP public-comment
processes; an ISO-style annual "State of Arizona Solar Waste" report
generated from `make real` each January.

## What NOT to do

- Don't lead with the compute number; its band is honest but wide.
- Don't average estimators or tighten bands cosmetically — the discipline
  *is* the differentiator.
- Don't scale to CAISO/ERCOT (they publish curtailment; nothing to estimate
  there except validation — useful later as an out-of-sample test of
  Estimator A against published truth, which IS worth doing).

## Status ledger

| Track | Status |
|---|---|
| 1. WEIM atlas | node availability verified; pull + per-BA reconciliation pending |
| 2. EIA filing | memo drafted (`docs/`); sending is the builder's call |
| 3. NSRDB re-run | S3 extraction running; sensitivity comparison pending |
| 4. Paper | real-data draft rendering; needs anchors + NSRDB + framing pass |
| 5. Explorer | live on Vercel (real data, 3 BAs) |
| 6. Anchors | 4 verified (one study); IRP mining not started |
