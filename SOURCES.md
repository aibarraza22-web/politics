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
