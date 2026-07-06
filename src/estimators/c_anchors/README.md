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

Populated in Phase 3. The header-only CSV here fixes the schema.
