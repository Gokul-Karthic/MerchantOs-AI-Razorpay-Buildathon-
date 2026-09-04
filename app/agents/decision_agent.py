from __future__ import annotations

import uuid

from app.ml.digital_twin import simulate_interventions
from app.ml.payguard import detect_incidents, incident_for_event
from app.ml.revenue import revenue_at_risk
from app.ml.risk_engine import score_event
from app.models.schemas import DecisionResponse, PaymentEvent
from app.services.actions import execute_payment_link_from_decision
from app.services.guardrails import evaluate_guardrails
from app.services.store import (
    append_audit,
    create_approval,
    list_events,
    save_decision,
)


def _choose_action(event: PaymentEvent, risk: float, options, incident, review_threshold: float) -> tuple[str, str]:
    if event.event_type != "payment.failed":
        return "monitor", "No recovery action is required for a non-failed payment."
    # Current experiment labels are unavailable in real operations and must not
    # influence action selection. RiskNet score is the operational signal.
    if risk >= review_threshold:
        return "escalate_review", "RiskNet reached the validated review threshold, so recovery automation is suppressed."

    viable = [o for o in options if o.action != "escalate_review"]
    best = max(viable, key=lambda o: o.expected_net_value_inr) if viable else None
    if not best:
        return "escalate_review", "No positive bounded intervention is available."

    # When a payment-method/bank incident is active, prefer a Payment Link if its
    # expected value is close to the mathematical best because it gives the test
    # customer a route to choose another payment method.
    payment_link = next((o for o in viable if o.action == "payment_link"), None)
    if incident and payment_link and payment_link.expected_net_value_inr >= best.expected_net_value_inr * 0.90:
        return "payment_link", f"PayGuard detected {incident.scope} degradation; a Test Mode Payment Link avoids forcing the degraded route."
    return best.action, f"Digital Twin selected {best.action.replace('_', ' ')} as the highest expected net-value bounded intervention."


def make_decision(event: PaymentEvent, *, auto_execute_test_action: bool = False) -> DecisionResponse:
    if not event.source.startswith("razorpay_test_mode"):
        raise ValueError("MerchantOS Decision Agent accepts Razorpay Test Mode events only")

    events = list_events()
    risk_detail = score_event(event, events)
    risk = float(risk_detail["risk_score"])
    review_threshold = float(risk_detail.get("review_threshold", 0.64))
    rar = revenue_at_risk(event, events)
    incidents = detect_incidents(events)
    incident = incident_for_event(event, incidents)
    options = simulate_interventions(event, events, risk_score=risk, revenue_at_risk=rar, incident=incident)
    action, reason = _choose_action(event, risk, options, incident, review_threshold)
    guard = evaluate_guardrails(event, risk_score=risk, action=action, review_threshold=review_threshold)

    # Guardrails have the final say over the recommendation.
    if guard.status == "BLOCKED" and action != "escalate_review":
        action = "escalate_review"
        reason += " Guardrails blocked provider execution and converted the outcome to review."
    if action == "monitor":
        guard_status = "OBSERVATION_ONLY"
        guard_text = "PASSED: observation-only"
    else:
        guard_status = guard.status
        guard_text = f"{guard.status}: {guard.reason}"

    chosen = next((o for o in options if o.action == action), None)
    simulation = {o.action: o.expected_recovery_inr for o in options}
    confidence = 0.99 if action == "monitor" else round(max(0.55, min(0.98, 0.68 + abs((chosen.expected_net_value_inr if chosen else 0.0)) / max(event.amount, 1) * 0.12 + risk * 0.08)), 4)

    audit_id = f"dec-{uuid.uuid4().hex[:12]}"
    approval_id = None
    if guard_status == "APPROVAL_REQUIRED":
        approval_id = f"appr-{uuid.uuid4().hex[:12]}"

    result = {
        "event_id": event.event_id,
        "risk_score": risk,
        "revenue_at_risk": rar,
        "recommended_action": action,
        "confidence": confidence,
        "reason": reason,
        "guardrail": guard_text,
        "guardrail_status": guard_status,
        "simulation": simulation,
        "digital_twin": [o.model_dump(mode="json") for o in options],
        "incident_id": incident.incident_id if incident else None,
        "approval_id": approval_id,
        "action_id": None,
        "learned_risk_score": risk_detail.get("learned_risk_score"),
        "deterministic_risk_score": risk_detail.get("deterministic_risk_score"),
    }
    save_decision(audit_id, result)
    if approval_id:
        create_approval(approval_id, audit_id, event.event_id, action, guard.reason)
    append_audit("decision", audit_id, "decision.created", {
        "event_id": event.event_id,
        "risk_score": risk,
        "revenue_at_risk": rar,
        "recommended_action": action,
        "guardrail_status": guard_status,
        "incident_id": result["incident_id"],
    })

    action_id = None
    if auto_execute_test_action and guard_status == "AUTO_ALLOWED_TEST" and action == "payment_link":
        executed = execute_payment_link_from_decision(audit_id)
        action_id = executed["action_id"]

    return DecisionResponse(
        audit_id=audit_id,
        action_id=action_id,
        event_id=event.event_id,
        risk_score=risk,
        revenue_at_risk=rar,
        recommended_action=action,
        confidence=confidence,
        reason=reason,
        guardrail=guard_text,
        guardrail_status=guard_status,
        simulation=simulation,
        digital_twin=options,
        incident_id=result["incident_id"],
        approval_id=approval_id,
        learned_risk_score=risk_detail.get("learned_risk_score"),
        deterministic_risk_score=risk_detail.get("deterministic_risk_score"),
    )
