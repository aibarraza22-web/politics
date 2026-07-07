# SOURCES.md — data source log

Every external data source used by this project, with access method, verification status, and retrieval dates. **Rule: no parser gets written until the source's live response has been inspected and logged here.**

Status legend: `unverified` = not yet accessed from this codebase · `verified` = live response inspected, schema notes recorded · `retrieved` = bulk pull cached under `data/raw/`.

| ID | Source | What we take | Access | Key needed | Status | First verified | Last retrieved |
|----|--------|--------------|--------|------------|--------|----------------|----------------|
| eia930 | EIA-930 Hourly Electric Grid Monitor | Hourly demand, net generation by fuel, interchange for BAs AZPS, SRP, TEPC (+ WALC for context). Imputed-hour flags must be handled explicitly. | EIA v2 API (`api.eia.gov/v2/electricity/rto/...`) | `EIA_API_KEY` (free) | unverified | — | — |
| eia860 | EIA-860 / 860M | AZ utility-scale solar plant inventory: lat/lon, AC/DC capacity, tracking type, in-service date | Annual XLSX bulk files + 860M monthly | none | unverified | — | — |
| eia923 | EIA-923 | Monthly per-plant net generation, for per-plant calibration of the potential model | Annual XLSX bulk files (also via EIA v2 API) | `EIA_API_KEY` for API path | unverified | — | — |
| nsrdb | NREL NSRDB (PSM v3+) | Hourly GHI/DNI/DHI + temperature at each plant location | NREL Developer API (`developer.nrel.gov`), rate-limited — cache aggressively to parquet | `NREL_API_KEY` (free) + email | unverified | — | — |
| oasis | CAISO OASIS | WEIM (EIM) locational prices at Arizona load-aggregation points; zero/negative-price hour analysis (Estimator B) | OASIS SingleZip API — **correct report name and AZ node naming must be investigated and documented here before building; do not trust the spec** | none | unverified | — | — |
| irps | APS / TEP IRPs, ACC eDocket, FERC filings, investor materials | Any stated curtailment figures or assumptions (Estimator C anchors) | Manual curation → `src/estimators/c_anchors/anchors.csv`, every row with source URL + quote | none | unverified | — | — |
| lit | LBNL 2024 data center energy report; EIA/LBNL curtailment literature (CAISO/ERCOT) | Methodological precedent + writeup context | Manual | none | unverified | — | — |

## Verification notes

*(Append dated notes here as each source is verified: exact endpoints used, response schema surprises, imputation-flag semantics, rate limits observed, node names found, etc.)*

- **2026-07-06 (Phase 0):** Log created. No external data sources accessed yet — the Phase 0 stub figure uses pvlib's clear-sky model (local computation, no API). Verification of eia930/eia860/eia923/nsrdb happens at the start of Phase 1/2; oasis at Phase 3.
- **2026-07-07 (Phases 1–5, demo build):** This build environment's network policy blocks every data host (www.eia.gov, api.eia.gov, developer.nrel.gov, oasis.caiso.com, even power.larc.nasa.gov all return proxy 403). Consequence: **all fetchers are written against documented schemas but remain `unverified-live`**, and the pipeline ships in demo mode on a synthetic fixture with injected ground truth (`src/demo_data.py`). This violates the "inspect real responses before writing parsers" rule out of necessity, so the rule converts into the checklist below — none of the real-mode fetchers may be trusted until it is done.

### Live-verification checklist (do on a networked machine, before `make real`)

1. **eia930** (`src/fleet/eia930.py`): pull one day for AZPS; eyeball raw JSON. Confirm route `electricity/rto/fuel-type-data`, field names (`respondent`, `fueltype`, `period`, `value`), units, and timezone of `period`. Resolve the imputation-flag gap: the v2 API exposes no flags — add the Grid Monitor bulk balance CSV path (which has them) or document why not.
2. **eia860** (`src/fleet/eia860.py`): download one vintage; diff the actual sheet + column names against the parser (`2___Plant_Y*`, `3_3_Solar_Y*`, "DC Net Capacity (MW)", tracking columns — EIA renames between vintages).
3. **eia923** (`src/fleet/eia923.py`): confirm route `electricity/facility-fuel`, facet names (`state`, `fuel2002`), and that monthly `generation` is net MWh.
4. **nsrdb**: not yet wired (demo weather stands in). Wire PSM v3 hourly at plant coordinates, cache per plant-year to parquet, respect rate limits.
5. **oasis** (`src/estimators/b_eim_prices.py`): investigate the correct WEIM report (`PRC_INTVL_LMP` is a guess) and the Arizona LAP/node names; record findings here. SPEC.md explicitly says do not trust the spec on this.
6. After each item: update the table above (status, dates) and re-run `make real && make test`.
