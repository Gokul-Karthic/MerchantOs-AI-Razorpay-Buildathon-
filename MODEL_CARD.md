# RiskNet Hybrid v2 — Model Card

## Intended use

Risk scoring for MerchantOS AI inside the Razorpay Test Mode Buildathon environment. The model supports review/escalation decisions and feeds Digital Twin + Decision Agent + Guardrails. It never executes a provider action directly.

## Data provenance

The one-time fitted artifact may use only genuine Razorpay Test Mode events from `merchantos.db` carrying controlled experiment labels. Synthetic and Live Mode rows are prohibited.

## Architecture

- Fixed behavioral policy score.
- Bayesian customer/instrument reputation fitted from historical controlled labels.
- Optional regularized logistic calibrator using leakage-safe temporal behavior features.
- Identity-quality detector suppresses device/IP evidence when localhost/browser identities collapse.

## Banned failure modes

- Current event label as a feature.
- Merchant event count / wall-clock chronology proxy as a learned feature.
- Constant localhost IP as fraud evidence.
- One browser device shared by the entire dataset as fraud evidence.
- Unknown payment instrument treated as a shared instrument.
- Learned candidate activation merely because training completed.
- All-positive/all-negative candidate activation.

## Learned calibrator quality gate

The holdout must contain both true positives and true negatives and satisfy minimum ROC-AUC, PR-AUC lift, precision, recall, and non-degenerate prediction behavior. If it fails, it is stored as rejected/inactive; RiskNet Hybrid v2 continues on the policy + Bayesian reputation path.

## Lifecycle

The finalized artifact is copied forward between releases. In v1.4.1, if the locked artifact is missing and `MERCHANTOS_ALLOW_MODEL_REFIT=false`, MerchantOS does not silently train; it keeps the operational policy fallback active and reports the missing artifact. Runtime outcomes remain auditable.

## Operational claim

Implementation-ready for the current MerchantOS Razorpay Test Mode system. It is not a claim that an 80-row sandbox dataset proves permanent fraud performance for arbitrary real merchants or future distribution shifts.
