from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.agents.decision_agent import make_decision
from app.ml.digital_twin import simulate_interventions
from app.ml.payguard import detect_incidents, incident_for_event
from app.ml.revenue import revenue_at_risk
from app.ml.risk_engine import score_event as operational_risk_score
from app.services.actions import verify_action
from app.services.store import (
    append_audit,
    get_approval,
    get_journey,
    latest_decision_for_event,
    list_actions_for_event,
    list_approvals_for_event,
    list_audit_events_for_entities,
    list_events,
    list_events_for_order,
    list_webhook_events_for_event_ids,
    update_journey,
    verify_audit_chain,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _status_for_trace(events: list[Any], decision: dict[str, Any] | None, actions: list[dict[str, Any]]) -> str:
    if any(a.get("status") == "VERIFIED_RECOVERED" for a in actions):
        return "RECOVERED"
    if any(a.get("status") in {"EXECUTED_TEST", "PENDING_VERIFICATION", "VERIFIED_PARTIAL"} for a in actions):
        return "RECOVERY_IN_PROGRESS"
    if decision:
        if decision.get("guardrail_status") == "BLOCKED":
            return "REVIEW_REQUIRED"
        if decision.get("guardrail_status") == "APPROVAL_REQUIRED":
            return "APPROVAL_REQUIRED"
        if decision.get("guardrail_status") == "AUTO_ALLOWED_TEST":
            return "READY_TO_ACT"
        return "DECIDED"
    if events:
        latest = events[-1]
        if latest.event_type == "payment.captured":
            return "PAID"
        if latest.event_type == "payment.authorized":
            return "AUTHORIZED"
        if latest.event_type == "payment.failed":
            return "FAILED"
        return "OBSERVED"
    return "AWAITING_PAYMENT"


def _timeline_item(
    *,
    at: str,
    stage: str,
    title: str,
    detail: str,
    tone: str = "info",
    source: str = "MerchantOS",
    technical: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "at": at,
        "stage": stage,
        "title": title,
        "detail": detail,
        "tone": tone,
        "source": source,
        "technical": technical or {},
    }


def project_journey(journey_id: str) -> dict[str, Any]:
    journey = get_journey(journey_id)
    if not journey:
        raise ValueError("journey not found")

    events = list_events_for_order(journey["order_id"])
    event_ids = [event.event_id for event in events]
    webhook_events = list_webhook_events_for_event_ids(event_ids)
    latest_event = events[-1] if events else None

    decision = latest_decision_for_event(latest_event.event_id) if latest_event else None
    decisions = []
    actions: list[dict[str, Any]] = []
    approvals: list[dict[str, Any]] = []
    if latest_event:
        from app.services.store import list_decisions_for_event

        decisions = list_decisions_for_event(latest_event.event_id)
        actions = list_actions_for_event(latest_event.event_id)
        approvals = list_approvals_for_event(latest_event.event_id)

    risk = None
    payguard_incident = None
    digital_twin: list[dict[str, Any]] = []
    if latest_event:
        all_events = list_events()
        risk = operational_risk_score(latest_event, [e for e in all_events if e.timestamp <= latest_event.timestamp] or all_events)
        incidents = detect_incidents(all_events)
        incident = incident_for_event(latest_event, incidents)
        payguard_incident = incident.model_dump(mode="json") if incident else None
        if latest_event.event_type == "payment.failed":
            rar = revenue_at_risk(latest_event, all_events)
            digital_twin = [
                option.model_dump(mode="json")
                for option in simulate_interventions(
                    latest_event,
                    all_events,
                    risk_score=float(risk["risk_score"]),
                    revenue_at_risk=rar,
                    incident=incident,
                )
            ]

    entity_pairs: list[tuple[str, str]] = [("journey", journey_id), ("order", journey["order_id"])]
    for event in events:
        entity_pairs.append(("payment", event.event_id))
    for d in decisions:
        entity_pairs.append(("decision", d["audit_id"]))
    for a in actions:
        entity_pairs.append(("action", a["action_id"]))
    for approval in approvals:
        entity_pairs.append(("approval", approval["approval_id"]))
    audit_events = list_audit_events_for_entities(entity_pairs, limit=600)

    timeline: list[dict[str, Any]] = []
    timeline.append(
        _timeline_item(
            at=journey["created_at"],
            stage="OBSERVE",
            title="Razorpay Test Mode order created",
            detail=f"₹{float(journey['amount']):,.2f} payment journey started. No synthetic payment row was created.",
            tone="info",
            source="MerchantOS → Razorpay",
            technical={"journey_id": journey_id, "order_id": journey["order_id"]},
        )
    )

    for audit_event in audit_events:
        if audit_event.get("entity_type") != "journey":
            continue
        event_type = audit_event.get("event_type")
        if event_type == "journey.checkout_opened":
            timeline.append(
                _timeline_item(
                    at=audit_event["created_at"],
                    stage="OBSERVE",
                    title="Razorpay Test Checkout opened",
                    detail="The customer entered the genuine Razorpay Test Mode checkout flow.",
                    tone="info",
                    source="MerchantOS Checkout",
                )
            )
        elif event_type == "journey.provider_refreshed":
            timeline.append(
                _timeline_item(
                    at=audit_event["created_at"],
                    stage="VERIFY",
                    title="Provider state refreshed",
                    detail="MerchantOS verified the latest payment state with the Razorpay Test Mode API.",
                    tone="neutral",
                    source="Razorpay API verification",
                )
            )

    for webhook in webhook_events:
        event_type = str(webhook.get("event_type") or "payment event")
        tone = "good" if event_type in {"payment.captured", "payment.authorized"} else "bad" if event_type == "payment.failed" else "info"
        human = event_type.replace("payment.", "Payment ").replace("_", " ").title()
        timeline.append(
            _timeline_item(
                at=str(webhook.get("received_at") or webhook.get("processed_at") or _iso_now()),
                stage="OBSERVE",
                title=human,
                detail="Signed Razorpay webhook observed and normalized by MerchantOS.",
                tone=tone,
                source="Signed Razorpay webhook",
                technical={"webhook_event_id": webhook.get("webhook_event_id"), "normalized_event_id": webhook.get("normalized_event_id")},
            )
        )

    if latest_event and risk:
        threshold = float(risk.get("review_threshold") or 0.64)
        score = float(risk.get("risk_score") or 0)
        timeline.append(
            _timeline_item(
                at=(decision or {}).get("created_at") or latest_event.timestamp.isoformat(),
                stage="UNDERSTAND",
                title="RiskNet assessed recovery safety",
                detail=f"Risk {score*100:.0f}% vs {threshold*100:.0f}% review threshold.",
                tone="bad" if score >= threshold else "good",
                source="RiskNet Hybrid v2",
                technical=risk,
            )
        )
        timeline.append(
            _timeline_item(
                at=(decision or {}).get("created_at") or latest_event.timestamp.isoformat(),
                stage="UNDERSTAND",
                title="Payment-health context checked",
                detail=(
                    f"PayGuard linked this payment to {payguard_incident['scope']} degradation."
                    if payguard_incident
                    else "No active PayGuard degradation was linked to this payment."
                ),
                tone="warn" if payguard_incident else "good",
                source="PayGuard",
                technical=payguard_incident or {},
            )
        )

    if latest_event and latest_event.event_type == "payment.failed" and digital_twin:
        best = max(digital_twin, key=lambda item: float(item.get("expected_net_value_inr") or -1e18))
        timeline.append(
            _timeline_item(
                at=(decision or {}).get("created_at") or latest_event.timestamp.isoformat(),
                stage="SIMULATE",
                title="Digital Twin compared recovery options",
                detail=f"Highest expected net-value option: {str(best.get('action') or '').replace('_', ' ')}.",
                tone="info",
                source="Digital Twin",
                technical={"options": digital_twin},
            )
        )

    if decision:
        guard = str(decision.get("guardrail_status") or "SIMULATION_ONLY")
        tone = "bad" if guard == "BLOCKED" else "warn" if guard == "APPROVAL_REQUIRED" else "good" if guard == "AUTO_ALLOWED_TEST" else "info"
        timeline.append(
            _timeline_item(
                at=decision["created_at"],
                stage="DECIDE",
                title="Decision Agent selected an intervention",
                detail=f"{str(decision.get('recommended_action') or '').replace('_', ' ').title()} — {decision.get('reason') or ''}",
                tone=tone,
                source="Decision Agent",
                technical={"audit_id": decision.get("audit_id"), "confidence": decision.get("confidence")},
            )
        )
        timeline.append(
            _timeline_item(
                at=decision["created_at"],
                stage="GUARD",
                title=f"Guardrail result: {guard.replace('_', ' ').title()}",
                detail=str(decision.get("guardrail") or "Deterministic guardrails evaluated the action boundary."),
                tone=tone,
                source="Deterministic Guardrails",
            )
        )

    for approval in approvals:
        status = str(approval.get("status") or "PENDING")
        timeline.append(
            _timeline_item(
                at=str(approval.get("decided_at") or approval.get("created_at") or _iso_now()),
                stage="GUARD",
                title=f"Human approval {status.lower()}",
                detail=str(approval.get("reason") or "Action required human approval."),
                tone="good" if status == "APPROVED" else "bad" if status == "REJECTED" else "warn",
                source="Approval Inbox",
                technical={"approval_id": approval.get("approval_id")},
            )
        )

    for action in actions:
        provider_url = (action.get("provider_payload") or {}).get("short_url")
        timeline.append(
            _timeline_item(
                at=str(action.get("executed_at") or action.get("created_at") or _iso_now()),
                stage="ACT",
                title="Razorpay Test Mode Payment Link created" if action.get("action_type") == "payment_link" else "Bounded action recorded",
                detail=(
                    f"Expected recovery ₹{float(action.get('expected_recovery') or 0):,.2f}."
                    + (" Recovery link is ready for the customer." if provider_url else "")
                ),
                tone="info",
                source="Razorpay Test Mode",
                technical={"action_id": action.get("action_id"), "provider_entity_id": action.get("provider_entity_id"), "short_url": provider_url},
            )
        )
        if action.get("verified_at"):
            recovered = action.get("status") == "VERIFIED_RECOVERED"
            timeline.append(
                _timeline_item(
                    at=str(action.get("verified_at")),
                    stage="VERIFY",
                    title="Recovery verified" if recovered else "Recovery outcome verified",
                    detail=f"Actual recovered value: ₹{float(action.get('actual_recovery') or 0):,.2f}. Status: {str(action.get('status') or '').replace('_', ' ').title()}.",
                    tone="good" if recovered else "warn",
                    source="Razorpay verification",
                    technical={"action_id": action.get("action_id")},
                )
            )
            timeline.append(
                _timeline_item(
                    at=str(action.get("verified_at")),
                    stage="LEARN",
                    title="Outcome recorded",
                    detail=f"MerchantOS stored expected ₹{float(action.get('expected_recovery') or 0):,.2f} vs actual ₹{float(action.get('actual_recovery') or 0):,.2f}.",
                    tone="good" if recovered else "info",
                    source="Learning & Outcomes",
                )
            )

    timeline.sort(key=lambda item: str(item.get("at") or ""))
    status = _status_for_trace(events, decision, actions)
    if journey.get("status") != status:
        update_journey(journey_id, status=status)
        journey = get_journey(journey_id) or journey

    payment = latest_event.model_dump(mode="json") if latest_event else None
    audit_chain = verify_audit_chain()
    return {
        "journey": journey,
        "status": status,
        "payment": payment,
        "events": [event.model_dump(mode="json") for event in events],
        "risk": risk,
        "payguard_incident": payguard_incident,
        "digital_twin": digital_twin,
        "decision": decision,
        "decisions": decisions,
        "approvals": approvals,
        "actions": actions,
        "webhooks": webhook_events,
        "timeline": timeline,
        "audit": {"chain_valid": bool(audit_chain.get("valid")), "records_checked": int(audit_chain.get("checked") or 0)},
        "safety": {
            "data_source": "razorpay_test_mode_only",
            "scenario_label": "UNLABELED",
            "synthetic_payment_created": False,
            "live_mode_allowed": False,
            "model_direct_execution": False,
        },
    }


def analyze_journey(journey_id: str, *, auto_execute_test_action: bool = False, force_redecide: bool = False) -> dict[str, Any]:
    trace = project_journey(journey_id)
    payment = trace.get("payment")
    if not payment:
        raise ValueError("No Razorpay payment has been observed for this journey yet")
    event_id = payment["event_id"]
    from app.services.store import get_event

    event = get_event(event_id)
    if not event:
        raise ValueError("payment event not found")
    if event.event_type != "payment.failed":
        append_audit("journey", journey_id, "journey.analysis_not_required", {"event_id": event_id, "event_type": event.event_type})
        return project_journey(journey_id)

    existing = latest_decision_for_event(event_id)
    if not existing or force_redecide:
        result = make_decision(event, auto_execute_test_action=auto_execute_test_action)
        append_audit(
            "journey",
            journey_id,
            "journey.analyzed",
            {"event_id": event_id, "audit_id": result.audit_id, "auto_execute_test_action": auto_execute_test_action},
        )
    return project_journey(journey_id)


def verify_journey(journey_id: str) -> dict[str, Any]:
    trace = project_journey(journey_id)
    verified: list[str] = []
    for action in trace.get("actions") or []:
        if action.get("provider_entity_type") != "payment_link":
            continue
        if action.get("status") in {"VERIFIED_RECOVERED", "VERIFIED_FAILED"}:
            continue
        verify_action(action["action_id"])
        verified.append(action["action_id"])
    append_audit("journey", journey_id, "journey.verify_requested", {"actions_checked": verified})
    return project_journey(journey_id)
