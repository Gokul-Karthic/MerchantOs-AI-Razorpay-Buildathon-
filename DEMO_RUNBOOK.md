# MerchantOS AI v1.4.1 — Demo Runbook

## 1. Start with Docker

```bash
bash scripts/prepare_docker_runtime.sh
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8501`.

## 2. Establish trust in 20 seconds

On **Overview** show:

- verified recovered revenue
- recovery performance vs expected
- Test Mode only
- Risk controls active
- audit verified

Explain: "MerchantOS does not blindly retry failures. It assesses risk, payment health and economics before a bounded action."

## 3. Live Payment Journey

Open **Live Payment Journey**.

1. Create a ₹499 Test Mode payment.
2. Click **Open Razorpay checkout**.
3. Complete a Razorpay Test Mode payment attempt.
4. Return to MerchantOS.
5. Click **Refresh from Razorpay** if the webhook has not populated yet.

For a failed payment:

6. Click **Analyze & decide**.
7. Show the one-page lifetime: RiskNet → PayGuard → Digital Twin → Decision Agent → Guardrail.
8. If the recommendation is an eligible Payment Link and Test actions are enabled, click **Analyze + bounded Test action**.
9. Open the generated recovery Payment Link and pay it in Test Mode.
10. Click **Verify recovery** if the webhook has not already verified it.
11. Show expected vs actual recovered value and audit validity on the same trace.

## 4. Safety story

Explain:

- live journeys are always `UNLABELED`
- experiment labels are not available to the live decision
- Live Mode is blocked
- RiskNet cannot execute
- only Test Mode Payment Links can execute
- medium cases require approval
- high-risk cases route to review

## 5. Close with business impact

Return to Overview / Learning & Outcomes and show provider-verified recovered revenue instead of model accuracy as the primary impact metric.
