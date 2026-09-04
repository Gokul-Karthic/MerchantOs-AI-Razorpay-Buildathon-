from __future__ import annotations

from app.ml.risk_model import score_components_for_event
from app.models.schemas import PaymentEvent


def score_event(event: PaymentEvent, events: list[PaymentEvent]) -> dict:
    components, status = score_components_for_event(event, events)
    risk = float(components.get("final_score") or 0.04)
    return {
        "risk_score": round(risk, 4),
        "deterministic_risk_score": round(float(components.get("policy_score") or risk), 4),
        "learned_risk_score": (
            round(float(components["calibrator_probability"]), 4)
            if components.get("calibrator_probability") is not None else None
        ),
        "active_ml_model": bool(status.get("learned_calibrator_active")),
        "model_version": status.get("model_version", "risknet-hybrid-v2"),
        "review_threshold": float(status.get("review_threshold", 0.64)),
        "critical_risk_threshold": float(status.get("critical_risk_threshold", 0.85)),
        "scoring_mode": "hybrid_policy_plus_validated_calibrator" if status.get("learned_calibrator_active") else "hybrid_policy_plus_bayesian_reputation",
    }
