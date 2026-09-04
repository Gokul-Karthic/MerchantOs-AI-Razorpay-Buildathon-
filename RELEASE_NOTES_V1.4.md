# MerchantOS AI v1.4 Release Notes

## Added

- Live Payment Journey workspace.
- Genuine Razorpay Test Mode order creation directly from the MerchantOS dashboard.
- MerchantOS-hosted Razorpay Test Checkout per journey.
- Per-payment lifetime trace across OBSERVE → UNDERSTAND → SIMULATE → DECIDE → GUARD → ACT → VERIFY → LEARN.
- Targeted journey refresh, analysis, and action verification endpoints.
- Journey traces use existing payment/webhook/decision/action/audit records rather than synthetic trace rows.
- Dockerfile and Docker Compose stack for FastAPI + Streamlit.
- Persistent `runtime/` state for SQLite + locked RiskNet artifact.
- API/dashboard health checks.
- Environment-configurable dashboard API URLs for container networking.
- Environment-configurable DB and artifact paths.
- Migration/runtime helper scripts and Makefile commands.

## Safety improvements

- Live journeys are always `UNLABELED`.
- Device/IP are stored as `unknown` for server-created journey orders instead of manufacturing browser identity evidence.
- Missing locked RiskNet artifact no longer causes silent training while `MERCHANTOS_ALLOW_MODEL_REFIT=false`; the safe operational fallback remains active.

## Unchanged

- Razorpay Test Mode only.
- Live Mode blocked.
- RiskNet cannot execute directly.
- Only guarded Test Mode Payment Links can execute.
- No synthetic payment rows.
