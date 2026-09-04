from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def _db_counts(path: Path) -> dict[str, int]:
    out: dict[str, int] = {}
    if not path.exists():
        return out
    with sqlite3.connect(path) as conn:
        for table in ["events", "payment_journeys", "decisions", "approvals", "actions", "audit_events", "razorpay_webhook_events"]:
            try:
                out[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.Error:
                out[table] = -1
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="MerchantOS local release-state check")
    parser.add_argument("--state-only", action="store_true", help="Only inspect persistent state; do not require provider configuration")
    args = parser.parse_args()

    db_path = Path(os.getenv("MERCHANTOS_DB_PATH", str(ROOT / "runtime" / "merchantos.db"))).expanduser()
    artifact_dir = Path(os.getenv("MERCHANTOS_ARTIFACT_DIR", str(ROOT / "runtime" / "artifacts"))).expanduser()
    model_path = artifact_dir / "risknet_hybrid_v2.joblib"
    manifest_path = artifact_dir / "risknet_hybrid_v2_manifest.json"
    counts = _db_counts(db_path)

    print("MerchantOS AI v1.4.1 readiness")
    print("DB:", db_path, "present=" + str(db_path.exists()))
    print("State counts:", counts)
    print("Locked model present:", model_path.exists())
    print("Model manifest present:", manifest_path.exists())

    critical: list[str] = []
    advisory: list[str] = []
    if not db_path.exists():
        critical.append("runtime database is missing")
    if not model_path.exists() or not manifest_path.exists():
        critical.append("locked RiskNet artifact/manifest is missing")

    if not args.state_only:
        from app.services.razorpay_client import RazorpayClient
        from app.services.store import verify_audit_chain
        from app.ml.risk_model import model_status

        client = RazorpayClient()
        print("Razorpay configured safely:", client.configured)
        print("Razorpay Test Mode key:", client.is_test_mode)
        print("Webhook secret configured:", bool(os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()))
        print("Test actions enabled:", os.getenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "false"))
        print("Automatic refit allowed:", os.getenv("MERCHANTOS_ALLOW_MODEL_REFIT", "false"))
        if not client.configured:
            critical.append("Razorpay Test Mode credentials are not safely configured")
        if not os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip():
            advisory.append("webhook secret is not configured")
        chain = verify_audit_chain() if db_path.exists() else {"valid": False}
        print("Audit chain:", chain)
        if not chain.get("valid"):
            critical.append("audit chain is invalid")
        status = model_status()
        print("RiskNet:", {k: status.get(k) for k in ["model_version", "active", "locked", "learned_calibrator_active", "review_threshold", "critical_risk_threshold"]})
        if status.get("model_version") != "risknet-hybrid-v2":
            critical.append("unexpected RiskNet model version")

    try:
        import sklearn
        print("scikit-learn runtime:", sklearn.__version__)
        if sklearn.__version__ != "1.7.1":
            advisory.append(f"scikit-learn {sklearn.__version__} differs from the locked artifact/runtime pin 1.7.1; use Docker or reinstall requirements")
    except Exception:
        advisory.append("scikit-learn is unavailable in this Python runtime; use Docker or install requirements")

    if counts.get("razorpay_webhook_events", 0) == 0:
        advisory.append("no signed webhook has been recorded in this runtime yet; API refresh may be doing all observation")
    if counts.get("actions", 0) == 0:
        advisory.append("no bounded provider action is recorded in this runtime yet")
    if counts.get("approvals", 0) == 0:
        advisory.append("human-approval path is not represented in this runtime evidence yet")

    for item in advisory:
        print("ADVISORY:", item)
    for item in critical:
        print("CRITICAL:", item)

    if critical:
        print("RESULT: NOT READY")
        return 2
    print("RESULT: CORE READY" if advisory else "RESULT: READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
