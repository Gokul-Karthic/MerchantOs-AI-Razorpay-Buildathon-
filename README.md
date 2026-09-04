
# MerchantOS AI

### AI Decision Layer for Autonomous Merchant Operations

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green)
![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red)
![Docker](https://img.shields.io/badge/Deployment-Docker-blue)
![Razorpay](https://img.shields.io/badge/Payments-Razorpay_Test_Mode-0C2451)
![Status](https://img.shields.io/badge/Buildathon-READY-brightgreen)

**MerchantOS AI** is an agentic payment-operations and revenue-recovery system built for the **Razorpay Buildathon**.

It helps merchants understand failed payments, identify payment-route problems, evaluate risk, simulate recovery strategies, choose the safest action, execute bounded Razorpay Test Mode actions, verify the actual result, and maintain a complete audit trail.

> **AI reasons. Guardrails decide whether it is safe to act. Razorpay confirms what actually happened.**

---

## Problem

A failed payment does not always mean that the customer should simply retry.

The actual issue may be:

- Customer or transaction risk
- A degraded bank route
- Payment-method issues
- Temporary provider failure
- A recovery action with poor expected value

MerchantOS AI treats payment recovery as a **decision problem**, not just a retry problem.

---

## Core MerchantOS Loop

```text
OBSERVE
   ↓
UNDERSTAND
   ↓
SIMULATE
   ↓
DECIDE
   ↓
GUARD
   ↓
ACT
   ↓
VERIFY
   ↓
LEARN

AUDIT runs across the complete lifecycle
````

### Complete Decision Flow

```text
Payment Failure
      ↓
RiskNet
      ↓
PayGuard
      ↓
Digital Twin
      ↓
Decision Agent
      ↓
Deterministic Guardrails
      ↓
Automatic Test Action
        OR
Human Approval
      ↓
Razorpay Verification
      ↓
Learning + Audit
```

---

## Main Features

| Component                   | Purpose                                          |
| --------------------------- | ------------------------------------------------ |
| **Overview**                | Merchant operations control room                 |
| **Live Payment Journey**    | Genuine Razorpay Test Mode payment flow          |
| **Payments**                | Payment evidence and transaction activity        |
| **RiskNet**                 | Hybrid transaction and customer risk assessment  |
| **PayGuard**                | Detect payment-method and bank-route degradation |
| **Digital Twin**            | Simulate recovery interventions                  |
| **Decision Agent**          | Choose the best recovery strategy                |
| **Guardrails**              | Deterministic financial safety controls          |
| **Safe Simulation**         | Generate decisions without provider execution    |
| **Bounded Test Mode Cycle** | Execute safe Razorpay Payment Link actions       |
| **Human Approval**          | Review sensitive or higher-value actions         |
| **Verify Pending Actions**  | Confirm provider-side recovery status            |
| **Learning & Outcomes**     | Compare expected vs actual recovery              |
| **Audit & Safety**          | Full traceability and system controls            |

---

## 1. Executive Overview

The Overview page acts as the MerchantOS control room.

It provides a quick view of:

* Payment activity
* Failed payments
* Recovery decisions
* Provider actions
* Verified recoveries
* Revenue at risk
* Payment health
* Risk state
* Approval activity
* System safety status

---

## 2. Live Payment Journey

MerchantOS AI works with **genuine Razorpay Test Mode transactions**.

A payment journey can be created through the application and completed using Razorpay checkout.

For a successful payment:

```text
Payment Successful
        ↓
No Recovery Required
```

For a failed payment:

```text
Payment Failed
      ↓
Recovery Analysis Begins
```

MerchantOS can also refresh the latest provider state directly from Razorpay.

This prevents unnecessary recovery actions on already successful payments.

---

## 3. Payments Intelligence

The Payments section provides the operational evidence used by MerchantOS AI.

It tracks:

* Amount
* Currency
* Payment method
* Bank
* Payment state
* Provider state
* Razorpay Payment ID
* Timestamp
* Success / Failure

Payments can be filtered to investigate failed transactions or payment-route issues.

---

## 4. RiskNet

### Hybrid Payment Risk Engine

RiskNet evaluates the risk associated with a payment before MerchantOS allows recovery actions.

It combines:

```text
Policy Signals
      +
Bayesian / Reputation Evidence
      +
Behavioral Features
      +
Identity Quality
      +
Optional Learned Calibration
```

Production model:

```text
risknet-hybrid-v2
```

Model type:

```text
hybrid_policy_bayesian_reputation_optional_logistic_calibrator
```

### Risk Behavior

Low-risk payments can continue through the recovery workflow.

Higher-risk payments may require:

```text
Review
   OR
Approval
   OR
Block
```

RiskNet itself **cannot directly execute Razorpay actions**.

It only provides risk evidence to the decision layer.

---

## RiskNet Model Performance

Final holdout metrics:

| Metric    | Result |
| --------- | -----: |
| Precision | 0.6667 |
| Recall    | 0.6667 |
| F1 Score  | 0.6667 |
| PR-AUC    | 0.7556 |
| ROC-AUC   | 0.9231 |
| Lift      | 4.0296 |

The locked RiskNet model was trained using:

```text
80 labeled genuine Razorpay Test Mode payments

20 controlled abuse cases
60 benign cases
3 payment methods
26 customer identities
```

No Live Mode rows were used.

No synthetic transaction rows were used in the final model dataset.

---

## 5. PayGuard

### Payment Route Health Intelligence

RiskNet asks:

> Is this transaction risky?

PayGuard asks:

> Is the payment route itself experiencing a problem?

PayGuard monitors:

* Recent payments
* Recent failures
* Failure rate
* Historical baseline
* Route degradation
* Incident severity
* Revenue at risk

### Example PayGuard Incident

```text
Recent payments: 3
Failures: 3
Recent failure rate: 100%
```

MerchantOS can identify that the payment route itself may be degraded.

This helps prevent the system from blindly recommending the same route again.

---

## 6. Digital Twin

Before MerchantOS performs an action, the **Digital Twin** simulates possible recovery strategies.

Possible interventions include:

```text
WAIT

RETRY

ALTERNATE PAYMENT METHOD

RAZORPAY PAYMENT LINK
```

For each strategy, it evaluates:

* Recovery probability
* Expected recovery value
* Cost
* Risk
* Payment-route health

MerchantOS then recommends the best expected recovery strategy.

> MerchantOS is **not hard-coded to always create a Payment Link**.

---

## 7. Decision Agent

The Decision Agent combines information from:

```text
RiskNet
+
PayGuard
+
Digital Twin
+
Payment State
+
Business Policy
```

It selects a recommended recovery strategy.

However, the AI does not have unrestricted financial authority.

Every decision must pass through MerchantOS Guardrails.

---

## 8. Deterministic Guardrails

Guardrails form the financial safety layer of MerchantOS AI.

They evaluate:

* Payment amount
* Risk score
* Confidence
* Recommended action
* Autonomy limits
* Approval requirement
* Provider action type
* Razorpay Test Mode status

Possible outcomes:

```text
AUTO_ALLOWED_TEST

APPROVAL_REQUIRED

SIMULATION_ONLY

BLOCKED
```

The AI can recommend an action.

The Guardrails decide whether the system is allowed to execute it.

---

## 9. Safe Simulation

MerchantOS includes a **Safe Simulation** mode.

This runs the intelligence pipeline without performing a real provider action.

```text
Analyze Payment
      ↓
Run RiskNet
      ↓
Check PayGuard
      ↓
Run Digital Twin
      ↓
Create Decision
      ↓
Apply Guardrails
```

No Razorpay Payment Link is created during Safe Simulation.

---

## 10. Decision Queue

The Decisions & Actions section provides visibility into MerchantOS recommendations.

For each case the merchant can inspect:

* Recommended action
* Risk
* Confidence
* Guardrail result
* Action state
* Approval state
* Provider result

This makes agent decisions visible instead of hiding them inside a black box.

---

## 11. Bounded Razorpay Test Mode Execution

MerchantOS currently allows one real provider-side action:

> **Razorpay Test Mode Payment Link creation**

The action can only happen when:

```text
Payment Failed
      ↓
Payment Link Recommended
      ↓
Risk Acceptable
      ↓
Guardrails Allow Execution
      ↓
Approval Not Required
      ↓
Create Razorpay Test Mode Payment Link
```

Other interventions such as retry, wait, or alternate payment method remain simulation recommendations.

---

## 12. Provider Action Idempotency

MerchantOS protects against duplicate Payment Link execution using:

```text
Existing Action Detection
+
Event-Level Checks
+
Atomic Provider Action Lock
```

Historical actions are preserved for audit purposes.

---

## 13. Human Approval

MerchantOS supports **human-in-the-loop financial automation**.

For higher-value or higher-risk cases:

```text
Decision
   ↓
Guardrails
   ↓
APPROVAL_REQUIRED
   ↓
Merchant Review
   ↓
Approve / Reject
```

This allows important financial actions to remain under human control.

---

## 14. Verify Pending Actions

MerchantOS checks Razorpay to verify the actual provider result.

Possible states include:

```text
PENDING

FAILED

PARTIALLY PAID

RECOVERED
```

This closes the decision loop:

```text
DECIDE
  ↓
ACT
  ↓
VERIFY
```

---

## Proven End-to-End Recovery

MerchantOS successfully demonstrated a complete recovery flow:

```text
Failed Payment
      ↓
RiskNet
      ↓
PayGuard
      ↓
Digital Twin
      ↓
Decision Agent
      ↓
Guardrails
      ↓
Razorpay Test Mode Payment Link
      ↓
Customer Completes Payment
      ↓
Razorpay Verification
      ↓
VERIFIED_RECOVERED
```

Example:

```text
Payment amount: ₹499

Expected recovery value:
₹155.47

Actual recovered amount:
₹499

Final state:
VERIFIED_RECOVERED
```

---

## 15. Learning & Outcomes

MerchantOS records:

```text
What the system expected
```

and compares it with:

```text
What actually happened
```

The system tracks:

* Decisions
* Provider actions
* Successful recoveries
* Expected recovery value
* Actual recovered revenue
* Realized vs expected performance

Operational outcomes are recorded without automatically retraining the locked RiskNet model.

---

## 16. Audit & Safety

Every important stage of the MerchantOS workflow is auditable.

Examples include:

* Payment Event
* Risk Assessment
* PayGuard Evidence
* Digital Twin Simulation
* Decision
* Guardrail Result
* Approval
* Provider Action
* Verification
* Learning Outcome

---

## Safety Architecture

MerchantOS was intentionally designed with strict financial safety controls.

```text
✓ Razorpay Test Mode only

✓ Live Mode execution blocked

✓ No fake payment injection for operational flows

✓ No LLM-generated financial evidence

✓ Deterministic financial calculations

✓ Deterministic Guardrails

✓ RiskNet cannot directly execute actions

✓ Human approval supported

✓ Provider action idempotency

✓ Automatic model retraining disabled

✓ Every important action is auditable
```

---

## Dashboard Modules

MerchantOS AI contains nine major sections:

```text
Overview

Live Payment Journey

Payments

Risk & Trust

Payment Health

Digital Twin

Decisions & Actions

Learning & Outcomes

Audit & Safety
```

Together they represent one connected merchant decision workflow.

---

## System Architecture

```text
                    ┌───────────────────────┐
                    │ Razorpay Test Mode    │
                    │ Checkout + Webhooks   │
                    └───────────┬───────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Payment Ingestion     │
                    │ + Journey Tracking    │
                    └───────────┬───────────┘
                                │
                  ┌─────────────┴─────────────┐
                  │                           │
                  ▼                           ▼
         ┌─────────────────┐         ┌─────────────────┐
         │     RiskNet     │         │    PayGuard     │
         │   Risk Engine   │         │  Route Health   │
         └────────┬────────┘         └────────┬────────┘
                  │                           │
                  └─────────────┬─────────────┘
                                ▼
                      ┌─────────────────┐
                      │  Digital Twin   │
                      │   Simulation    │
                      └────────┬────────┘
                               ▼
                      ┌─────────────────┐
                      │ Decision Agent  │
                      └────────┬────────┘
                               ▼
                      ┌─────────────────┐
                      │   Guardrails    │
                      └────────┬────────┘
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
        ┌───────────────────┐     ┌───────────────────┐
        │ AUTO_ALLOWED_TEST │     │ APPROVAL_REQUIRED │
        └─────────┬─────────┘     └─────────┬─────────┘
                  │                         │
                  └────────────┬────────────┘
                               ▼
                    ┌────────────────────┐
                    │ Razorpay Test Mode │
                    │   Payment Link     │
                    └─────────┬──────────┘
                              ▼
                    ┌────────────────────┐
                    │      Verify        │
                    │ Provider Outcome   │
                    └─────────┬──────────┘
                              ▼
                    ┌────────────────────┐
                    │ Learning & Audit   │
                    └────────────────────┘
```

---

## Tech Stack

| Component            | Technology                                     |
| -------------------- | ---------------------------------------------- |
| Programming Language | Python                                         |
| Backend              | FastAPI                                        |
| Dashboard            | Streamlit                                      |
| Machine Learning     | scikit-learn                                   |
| Risk Model           | Hybrid Policy + Bayesian + Learned Calibration |
| Database             | SQLite                                         |
| Payment Provider     | Razorpay Test Mode                             |
| API Documentation    | Swagger / OpenAPI                              |
| Containerization     | Docker                                         |
| Orchestration        | Docker Compose                                 |
| Testing              | pytest                                         |
| Local Webhooks       | Cloudflare Tunnel                              |

---

## Project Structure

```text
MerchantOS_AI/
│
├── app/
│   ├── agents/
│   │   └── decision_agent.py
│   ├── api/
│   │   └── routes.py
│   ├── ml/
│   │   ├── digital_twin.py
│   │   ├── payguard.py
│   │   ├── revenue.py
│   │   ├── risk_engine.py
│   │   ├── risk_graph.py
│   │   ├── risk_graph_features.py
│   │   ├── risk_hybrid_features.py
│   │   └── risk_model.py
│   ├── services/
│   │   ├── actions.py
│   │   ├── guardrails.py
│   │   ├── journeys.py
│   │   ├── learning.py
│   │   ├── orchestrator.py
│   │   ├── privacy.py
│   │   ├── razorpay_client.py
│   │   ├── razorpay_ingestion.py
│   │   └── store.py
│   ├── dashboard.py
│   └── main.py
│
├── artifacts/
│   ├── risknet_hybrid_v2.joblib
│   └── risknet_hybrid_v2_manifest.json
│
├── scripts/
├── tests/
├── ARCHITECTURE.md
├── MODEL_CARD.md
├── DEMO_RUNBOOK.md
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Installation

### Clone the Repository

```bash
git clone https://github.com/Gokul-Karthic/MerchantOs-AI-Razorpay-Buildathon-.git
```

```bash
cd MerchantOs-AI-Razorpay-Buildathon-
```

---

## Environment Configuration

Create your `.env` file:

```bash
cp .env.example .env
```

Configure your own Razorpay Test Mode credentials.

```env
RAZORPAY_KEY_ID=your_test_key_id
RAZORPAY_KEY_SECRET=your_test_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret

MERCHANTOS_HASH_SALT=your_private_stable_salt
MERCHANTOS_ALLOW_MODEL_REFIT=false
```

> Never commit real `.env` credentials to GitHub.

---

## Run With Docker

```bash
docker compose up -d --build
```

Check containers:

```bash
docker compose ps
```

---

## Open MerchantOS

### Dashboard

```text
http://localhost:8501
```

### Swagger API

```text
http://localhost:8000/docs
```

### Health Check

```text
http://localhost:8000/health
```

---

## Razorpay Webhooks

For local development:

```bash
cloudflared tunnel --url http://localhost:8000
```

Webhook endpoint:

```text
/api/razorpay/webhook
```

Example:

```text
https://your-tunnel.trycloudflare.com/api/razorpay/webhook
```

Configure this URL inside Razorpay **Test Mode** webhook settings.

---

## Testing

Run tests:

```bash
pytest -q
```

Final validated build:

```text
37 tests passed
```

Run the readiness check:

```bash
python scripts/system_check.py
```

Expected output:

```text
RESULT: READY
```

---

## Demo Flow

```text
Create Razorpay Test Mode payment
            ↓
Payment fails
            ↓
RiskNet evaluates risk
            ↓
PayGuard checks route health
            ↓
Digital Twin simulates recovery options
            ↓
Decision Agent selects strategy
            ↓
Guardrails evaluate safety
            ↓
Safe Simulation
      OR
Bounded Test Mode Action
            ↓
Payment Link
            ↓
Customer pays
            ↓
Razorpay verifies result
            ↓
VERIFIED_RECOVERED
            ↓
Learning & Outcomes
            ↓
Audit & Safety
```

---

## What Makes MerchantOS AI Different?

MerchantOS AI is **not simply an LLM connected to a payment API**.

It combines:

* Real Razorpay Test Mode payment evidence
* RiskNet risk intelligence
* PayGuard payment-route health
* Digital Twin simulation
* Agentic decision-making
* Deterministic Guardrails
* Human approval
* Bounded provider execution
* Provider-side verification
* Outcome learning
* Auditability

The goal is not simply to automate more actions.

The goal is to automate the **right action safely**.

---

## Current Scope

MerchantOS AI is intentionally restricted to:

```text
✓ Razorpay Test Mode Payment Link

✗ Razorpay Live Mode Execution
```

The following remain simulated recovery recommendations:

```text
WAIT

RETRY

ALTERNATE PAYMENT METHOD
```

This is an intentional safety design.

---

## Buildathon Use Case

### AI Revenue Recovery

MerchantOS AI demonstrates how AI agents can safely participate in merchant financial operations while preserving:

* AI reasoning
* Deterministic controls
* Human oversight
* Provider verification
* Auditability
* Business outcome measurement

---

## Demo Video

Add your final YouTube link here:


Video Demo:
(https://drive.google.com/file/d/12cC9pwKAzqnRRitzVF5WjA7MTN9PRW6F/view))


---

## Author

### Gokul Karthic

GitHub:
[https://github.com/Gokul-Karthic](https://github.com/Gokul-Karthic)

Project Repository:
[https://github.com/Gokul-Karthic/MerchantOs-AI-Razorpay-Buildathon-](https://github.com/Gokul-Karthic/MerchantOs-AI-Razorpay-Buildathon-)

---

