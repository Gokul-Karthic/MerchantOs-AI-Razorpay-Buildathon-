# Live Payment Journey / Decision Trace

The Live Payment Journey is a first-class operational trace, not a synthetic demo mode.

## What is created

`POST /api/journeys` creates a real Razorpay **Test Mode** order. MerchantOS saves only the local journey/order context required to correlate later provider events. No local payment event is invented.

Live journeys are forced to `UNLABELED`. Controlled experiment labels remain offline-only model training/evaluation metadata.

## API surface

- `POST /api/journeys` — create a Test Mode journey/order.
- `GET /api/journeys` — list live journeys.
- `GET /api/journeys/{journey_id}` — complete projected trace.
- `POST /api/journeys/{journey_id}/checkout-opened` — audit checkout entry.
- `POST /api/journeys/{journey_id}/refresh` — verify order/payments from Razorpay API.
- `POST /api/journeys/{journey_id}/analyze` — targeted RiskNet/PayGuard/Digital Twin/Decision/Guardrail evaluation.
- `POST /api/journeys/{journey_id}/verify` — verify provider recovery actions for that journey.
- `/journey-checkout/{journey_id}` — MerchantOS-hosted Razorpay Test Checkout.

## Trace projection

The timeline is projected from real system records rather than maintained as a fake parallel state machine:

- journey/order creation audit
- signed Razorpay webhook history
- Razorpay API verification/backfill
- normalized payment state
- RiskNet score
- PayGuard incident context
- Digital Twin options
- Decision Agent output
- Guardrail state
- human approval state
- Razorpay Test Mode Payment Link action
- provider verification/recovery
- expected-vs-actual outcome
- global audit-chain integrity

## Why this is useful

A judge or merchant can select one payment and understand its entire lifetime without jumping across eight dashboards. The same underlying payment still appears in the specialist RiskNet, PayGuard, Digital Twin, Decisions, Learning, and Audit views.
