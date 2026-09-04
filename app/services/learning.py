from __future__ import annotations

from app.ml.risk_model import dataset_readiness, model_status
from app.services.store import list_actions, list_approvals, list_decisions, list_events


def learning_status() -> dict:
    events = list_events()
    actions = list_actions(limit=5000)
    decisions = list_decisions(limit=5000)
    approvals = list_approvals(limit=5000)
    provider_actions = [a for a in actions if a.get("execution_mode") == "razorpay_test_mode"]
    recovered = [a for a in provider_actions if float(a.get("actual_recovery") or 0) > 0]
    expected = sum(float(a.get("expected_recovery") or 0) for a in provider_actions)
    actual = sum(float(a.get("actual_recovery") or 0) for a in provider_actions)
    pending_approvals = sum(a.get("status") == "PENDING" for a in approvals)
    return {
        "data_source": "razorpay_test_mode_only",
        "risknet_training_readiness": dataset_readiness(events),
        "risknet_model": model_status(events),
        "operational_outcomes": {
            "decisions": len(decisions),
            "actions_total": len(actions),
            "razorpay_test_mode_actions": len(provider_actions),
            "recovered_actions": len(recovered),
            "expected_recovery_inr": round(expected, 2),
            "actual_recovery_inr": round(actual, 2),
            "realized_vs_expected_ratio": round(actual / expected, 4) if expected else None,
            "pending_approvals": pending_approvals,
        },
        "learning_policy": "RiskNet Hybrid v2 is finalized once from the existing controlled Razorpay Test Mode dataset and locked. Runtime outcomes are logged; automatic retraining is disabled by default.",
    }
