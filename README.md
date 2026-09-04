# MerchantOS AI v1.4.1 — Reconciled Buildathon Final

**MerchantOS AI is the AI decision layer for safe Razorpay merchant revenue recovery.**

`OBSERVE → UNDERSTAND → SIMULATE → DECIDE → GUARD → ACT → VERIFY → LEARN`

v1.4.1 keeps the finalized `risknet-hybrid-v2` architecture and adds two product-maturity features:

1. **Live Payment Journey / Decision Trace** — create a genuine Razorpay Test Mode order from MerchantOS and follow one payment from creation through provider events, RiskNet, PayGuard, Digital Twin, Decision Agent, Guardrails, recovery action, verification, learning, and audit.
2. **Dockerized runtime** — FastAPI and Streamlit run as a reproducible two-service stack with persistent SQLite/model storage and health checks.

## Non-negotiable safety policy

- Razorpay **Test Mode only** (`rzp_test_...`).
- Live Mode keys are refused.
- Live Payment Journey creates **real Razorpay Test Mode orders/payments**, not synthetic payment rows.
- Live journeys are always `UNLABELED`; experiment labels cannot be supplied to the live journey workflow.
- Synthetic artifacts are forbidden as active RiskNet inputs.
- RiskNet cannot execute provider actions directly.
- Provider execution is limited to guarded Razorpay Test Mode Payment Links.
- The locked RiskNet artifact does **not** silently retrain when `MERCHANTOS_ALLOW_MODEL_REFIT=false`.

## Live Payment Journey

Open **Live Payment Journey** in the dashboard. The flow is:

1. Enter an amount and optional customer reference.
2. MerchantOS calls Razorpay Test Mode and creates a real order.
3. Open the MerchantOS-hosted Razorpay Test Checkout.
4. Complete or fail the Test Mode payment.
5. Signed webhooks remain the primary observation; **Refresh from Razorpay** is API verification/backfill.
6. If the payment failed, click **Analyze & decide**. MerchantOS shows RiskNet, PayGuard, Digital Twin options, Decision Agent recommendation, and Guardrail result.
7. If Test actions are enabled and the case is eligible, **Analyze + bounded Test action** may create a Razorpay Test Mode Payment Link.
8. Complete the recovery link and click **Verify recovery** if needed.
9. The same page displays the complete payment lifetime and audit-backed decision trace.

No training label is used in this workflow.

## Upgrade from your working v1.3.2

After extracting v1.4.1:

```bash
cd ~/Downloads/MerchantOS_AI_v1.4.1_ReconciledBuildathonFinal
bash scripts/migrate_from_previous.sh ../MerchantOS_AI_v1.3.2_AlwaysVisibleSidebar
```

This copies your `.env`, current `merchantos.db`, and locked RiskNet artifact. It does **not** retrain the model.


## One-command reconciliation check

After migrating your local state, run:

```bash
python3 scripts/system_check.py
```

It checks the runtime DB, locked RiskNet artifact, Test Mode configuration, audit-chain validity, and reports advisory gaps such as no webhook/action evidence yet.

**Submission safety:** this clean archive intentionally does not contain `.env`, `merchantos.db`, or `runtime/`. Keep those local.

## Recommended: Docker startup

Docker Desktop is the only runtime prerequisite.

```bash
cd ~/Downloads/MerchantOS_AI_v1.4.1_ReconciledBuildathonFinal
bash scripts/prepare_docker_runtime.sh
docker compose up --build -d
```

Then open:

- Dashboard: `http://localhost:8501`
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

Useful commands:

```bash
docker compose ps
docker compose logs -f --tail=100
docker compose down
```

Or with `make`:

```bash
make docker-up
make docker-status
make docker-logs
make docker-down
```

The API and dashboard are separate containers. The dashboard talks to the API over the internal Docker network, while browser-facing checkout links use `http://localhost:8000`.

### Docker persistence

`bash scripts/prepare_docker_runtime.sh` creates:

```text
runtime/
├── merchantos.db
└── artifacts/
    ├── risknet_hybrid_v2.joblib
    └── risknet_hybrid_v2_manifest.json
```

`runtime/` is bind-mounted into the API container and is gitignored. Rebuilding the Docker image does not erase your payment history or locked model.

## Local Python startup (optional)

If you do not use Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
python -m uvicorn app.main:app --reload
```

Second terminal:

```bash
source .venv/bin/activate
python -m streamlit run app/dashboard.py
```

## Environment

Copy `.env.example` to `.env` and configure your **Razorpay Test Mode** credentials and webhook secret. Never commit `.env`.

Important settings:

```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
MERCHANTOS_HASH_SALT=...
MERCHANTOS_TEST_ACTIONS_ENABLED=false
MERCHANTOS_ALLOW_MODEL_REFIT=false
MERCHANTOS_DASHBOARD_PUBLIC_URL=http://localhost:8501
```

Set `MERCHANTOS_TEST_ACTIONS_ENABLED=true` only when you intentionally want eligible Test Mode Payment Links to execute.

## RiskNet behavior when the artifact is missing

v1.4.1 does **not** silently fit a new model in normal operation. If the locked artifact is missing while `MERCHANTOS_ALLOW_MODEL_REFIT=false`, MerchantOS remains available using its safe policy/reputation fallback and reports the missing artifact. Copy the finalized artifact from your previous working build.

## Validation

Run:

```bash
pytest -q
```

The v1.4.1 package contains regression tests for the existing closed loop, no-label-leak safety, threshold alignment, Live Payment Journey, and Docker packaging.

## Main workspaces

- **Overview** — business impact and current state.
- **Live Payment Journey** — create and trace a genuine Test Mode payment end-to-end.
- **Payments** — provider ingestion and payment activity.
- **Risk & Trust** — RiskNet scoring and graph evidence.
- **Payment Health** — PayGuard degradation and RCA.
- **Digital Twin** — intervention simulation.
- **Decisions & Actions** — Guardrails, approvals, Test Mode actions.
- **Learning & Outcomes** — expected vs actual recovery.
- **Audit & Safety** — hash-chain integrity and safety boundaries.

## Buildathon positioning

MerchantOS is primarily an **AI Revenue Recovery** product with integrated RiskNet safety. The live journey makes that story demonstrable in one payment: observe a real Test Mode failure, assess risk, simulate recovery options, guard the action, execute only a bounded provider action, verify recovery, and audit the entire lifetime.
