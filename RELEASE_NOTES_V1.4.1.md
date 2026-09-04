# MerchantOS AI v1.4.1 — Reconciled Buildathon Final

This release is a reconciliation/hardening pass over v1.4. It does not add another agent or retrain RiskNet.

## Correctness fixes

- Added `GUARD` to the API-level closed-loop sequence so API, dashboard, docs and architecture agree.
- Live Payment Journey successful payments remain a safe no-op for recovery analysis; regression coverage was added.
- New Payment Link actions now store the Digital Twin's expected recovery for the chosen intervention, rather than the broader revenue-at-risk estimate.
- The explicit RiskNet training endpoint now refuses refit while `MERCHANTOS_ALLOW_MODEL_REFIT=false`.

## Governance/UI reconciliation

- Learning & Outcomes now separates:
  - locked model training evidence from the finalized artifact, and
  - the current operational Test Mode dataset.
- This prevents new `UNLABELED` live payments from making the locked training evidence appear to have disappeared.

## Packaging/migration hardening

- `.env`, SQLite runtime state and local backup files are excluded from the submission-safe release.
- Migration now prefers the richest operational DB available (`runtime/merchantos.db` when present) rather than blindly copying a possibly empty packaged DB.
- Migration prefers runtime model artifacts when present and copies them without retraining.
- Added `scripts/system_check.py` for one-command readiness/state diagnostics.
- Added package hygiene ignores for `*.backup`, `*.save` and macOS archive metadata.

## Validation

- 37 regression tests pass.
- Python compilation passes.
- User-host Docker smoke test previously showed API and dashboard containers healthy.
- No synthetic active payment inputs and no Live Mode execution were introduced.
