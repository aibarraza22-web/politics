# Data-quality report: AZPS solar in EIA-930 is unattributable to its utility-scale fleet

**Prepared:** 2026-07-07 · **Contact:** [builder] · **Replication:** this repository (`make real`; evidence table = `reconciliation` in `data/c2c.duckdb`)

*Draft memo for submission to EIA's Grid Monitor team ([EIA-930 contact form / grid-monitor@eia.gov]) and for the working paper's appendix. Every number regenerates from public data with two free API keys.*

## Summary

Arizona Public Service's (BA code **AZPS**) hourly solar generation series in EIA-930 exceeds the summed monthly net generation (EIA-923) of **every utility-scale PV plant attributable to AZPS in EIA-860** by a large, growing margin — 40% in 2022, 57% in 2023, 74% in 2024 — while the neighboring Arizona BAs (SRP, TEPC) reconcile within a few percent using identical methodology. We believe AZPS's 930 fuel-level solar reporting includes estimated small-scale/distributed generation, which EIA-930 documentation says should be excluded, and which makes the series unusable for fleet-level analysis without a documented reporting basis.

## Evidence

Annual energy, 930 (Adjusted, imputed hours excluded and coverage-rescaled) vs. 923 (per-plant PV, plants assigned to each BA by EIA-860 "Balancing Authority Code", 2024 vintage):

| BA | Year | 930 (GWh) | Σ923 fleet (GWh) | Gap |
|----|------|-----------|------------------|-----|
| AZPS | 2022 | 1,637 | 1,167 | **+40%** |
| AZPS | 2023 | 1,729 | 1,104 | **+57%** |
| AZPS | 2024 | 2,967 | 1,703 | **+74%** |
| SRP | 2022 | 1,133 | 1,151 | −1.6% |
| SRP | 2023 | 1,548 | 1,592 | −2.8% |
| SRP | 2024 | 3,372 | 3,376 | −0.1% |
| TEPC | 2022 | 1,066 | 1,085 | −1.8% |
| TEPC | 2023 | 1,014 | 1,042 | −2.7% |
| TEPC | 2024 | 985 | 1,069 | −7.9% |

Supporting observations:

1. **Physically impossible implied capacity factor.** AZPS's 2024 930 solar (2,967 GWh) against its 919 MW AC of 860-assigned utility-scale PV implies a ~37% annual capacity factor — above the physical ceiling for any fixed/single-axis PV fleet at Arizona's latitude.
2. **Reattribution cannot explain it.** Arizona hosts ~1.8 GW of utility PV assigned to CISO and ~160 MW to WALC (Agua Caliente, the Mesquite complex, Sun Streams, McFarland). A non-negative least-squares fit of AZPS's monthly 930−923 gap onto these plants' monthly generation profiles produces non-physical weights (small plants at 4–6×; R² 0.78) — no plant subset closes the gap.
3. **The gap's growth pattern tracks distributed-solar adoption**, smooth and monotonic, rather than utility-plant commissioning steps.
4. **Isolated impossible hours are also present and unflagged**, e.g. 2024-01-25 17:00 UTC: 3,822 MW reported solar (4.2× fleet nameplate, on a January morning), with no imputation flag in the bulk balance file.

## Questions for EIA / APS

1. What is AZPS's reporting basis for fuel-level solar in Form 930 — does it include estimated behind-the-meter or non-utility-scale distributed generation, and since when?
2. If so, can the distributed component be flagged or published separately (as CAISO's BTM estimates are), so the utility-scale series is recoverable?
3. Can the 2024-01-25 spike hours be corrected or flagged?

## Why it matters

EIA-930 is the only public hourly generation record for Arizona's BAs. Any analysis of solar curtailment, renewable integration, or resource adequacy that uses AZPS's solar series inherits this discrepancy silently. In our curtailment study it forced excluding Arizona's largest utility from physical-model estimation entirely — the union of these issues means **no one can currently audit how much solar Arizona's largest BA actually produces or wastes**.
