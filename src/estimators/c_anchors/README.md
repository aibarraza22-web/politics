# Estimator C — documented curtailment anchors

Hand-curated ground-truth anchors from utility IRPs (APS/TEP), ACC eDocket
filings, FERC filings, and investor materials. These sanity-check estimators
A and B; they are never merged or averaged into them.

Rules (from SPEC.md §2):

- **Every row must carry a source URL and an exact quote.** No paraphrased
  numbers, no rows without provenance.
- `curtailment_type` is one of `economic`, `physical`, `unspecified` — record
  what the source actually says, not what we infer.
- `curtailment_value` + `unit` as stated in the source (MWh, %, GWh/yr, …);
  do not convert in this file — conversion happens in code where it's tested.
- `retrieved_date` = the date the document was accessed (YYYY-MM-DD).
- If a source gives a projection/assumption rather than a measurement, say so
  in `notes`.

The header-only `anchors.csv` fixes the schema and holds only **verified**
anchors (quote checked against the source document by a human).

`candidates.csv` holds real leads found via web search whose quotes could
not yet be verified verbatim (this build environment cannot fetch the source
documents). Promotion path: open the source URL, confirm the exact quote and
figure, move the row into `anchors.csv` with the verbatim quote and today's
date. Candidates are **never** loaded by the pipeline (`load.py` reads
`anchors.csv` only) — unverified numbers stay out of every figure.

Best current lead: NREL/CP-6A20-74176 (O'Shaughnessy, Cruce & Xu) — APS 2018
curtailment ≈ 17,100 MWh ≈ 2.9% of potential, described as entirely economic
(EIM negative pricing), peaking March–April. Its companion dataset
(data.nrel.gov/submissions/116) may yield more Arizona anchors.
