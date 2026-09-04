# MerchantOS AI — Reconciliation Audit

## What was verified from the uploaded v1.4 project

- Python source compilation: PASS.
- Existing regression suite: 35/35 PASS before reconciliation.
- Reconciled regression suite: 37/37 PASS.
- FastAPI startup smoke test: PASS.
- API health and audit verification: PASS.
- Safe GET smoke checks across Overview, Events, RiskNet, PayGuard, Digital Twin, Learning, Audit, Journeys and Razorpay status: PASS.
- SQLite `PRAGMA integrity_check`: PASS for the uploaded runtime DB.
- Audit hash chain in the uploaded runtime DB: VALID (150 records at audit time).
- Locked `risknet-hybrid-v2` artifact: present and active.
- Runtime review threshold resolves to 0.64 and critical tier to 0.85.
- Live Mode key rejection, manual event-ingestion block, webhook signature verification/idempotency, no-label-leak, high-risk block, human-approval policy and bounded Payment Link execution are covered by regression tests.
- Docker API and dashboard were reported healthy in the user's host-level `docker compose ps` output.

## Uploaded runtime-state snapshot

The uploaded v1.4 Docker runtime contained:

- 93 Razorpay Test Mode payment observations.
- 60 captured, 32 failed, 1 created.
- 5 Live Payment Journeys.
- 3 recorded decisions.
- 0 provider actions.
- 0 approvals.
- 0 signed webhook records.
- 150 valid audit records.

All 93 current operational observations were `UNLABELED` and API-synced. The locked model artifact still contains its original finalized training evidence (80 labeled Test Mode observations, 26 customers, quality-gated calibrator and held-out metrics). v1.4.1 explicitly separates these two concepts in the UI.

## Important runtime evidence still to demonstrate on the user's Mac

These are not unfinished code paths; they are external/live integration branches that were not present in the uploaded runtime evidence:

1. A signed Razorpay webhook arriving through the public tunnel at `/api/razorpay/webhook`.
2. A new bounded Test Mode Payment Link action from the v1.4/v1.4.1 runtime.
3. Provider verification of that recovery action.
4. A live human-approval example, if desired for the demo.

The code paths are regression-tested, but a Buildathon demo is stronger after at least one fresh live run records them in the current runtime DB.

## Submission safety finding

The uploaded ZIP contained a real `.env` with configured Razorpay Test Mode credentials, webhook secret and local hash salt. The values were not copied into this release and are not printed in this report. Never submit or commit that `.env`. If that ZIP has been shared outside your private environment, rotate those Test Mode credentials/secrets before submission.

## Scope note

MerchantOS is Buildathon-mature and intentionally Test-Mode bounded. It is not presented as a production Razorpay replacement. Production deployment would additionally require organization authentication/authorization, secret management, observability/alerting, deployment infrastructure, rate limiting and operational runbooks.
