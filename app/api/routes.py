from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Literal

import requests
from fastapi import APIRouter, Header, HTTPException, Request

from app.agents.decision_agent import make_decision
from app.ml.digital_twin import simulate_interventions
from app.ml.payguard import detect_incidents, incident_for_event
from app.ml.revenue import revenue_at_risk
from app.ml.risk_engine import score_event as operational_risk_score
from app.ml.risk_graph import cluster_summary
from app.ml.risk_model import (
    dataset_readiness,
    learned_scores_for_events,
    model_status,
    train_testmode_model,
)
from app.models.schemas import (
    ApprovalDecisionRequest,
    DecisionRequest,
    OrchestratorRunRequest,
    PaymentJourneyCreateRequest,
    JourneyAnalyzeRequest,
    RazorpayOrderCreateRequest,
    RazorpaySyncRequest,
    RiskCluster,
    RiskGraphScore,
    RiskModelTrainRequest,
)
from app.services.actions import (
    execute_payment_link_from_decision,
    update_action_from_payment_link_webhook,
    verify_action,
)
from app.services.learning import learning_status
from app.services.journeys import analyze_journey, project_journey, verify_journey
from app.services.orchestrator import run_cycle
from app.services.privacy import stable_hash
from app.services.razorpay_client import RazorpayClient
from app.services.razorpay_ingestion import (
    normalize_payment_entity,
    payment_from_webhook,
    payment_link_from_webhook,
)
from app.services.store import (
    append_audit,
    claim_webhook_event,
    clear_non_razorpay_events,
    dataset_status,
    decide_approval,
    find_action_by_provider_id,
    get_action,
    get_approval,
    get_decision,
    get_event,
    get_journey,
    get_order_context,
    init_db,
    list_actions,
    list_approvals,
    list_audit_events,
    list_decisions,
    list_events,
    list_incidents,
    list_journeys,
    list_order_contexts,
    list_webhook_events,
    mark_webhook_processed,
    save_incidents,
    save_journey,
    save_order_context,
    update_journey,
    upsert_event,
    verify_audit_chain,
    webhook_stats,
)

router = APIRouter()


def _client() -> RazorpayClient:
    return RazorpayClient()


def _provider_call(fn):
    try:
        return fn()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 502
        detail = "Razorpay Test Mode API request failed"
        if exc.response is not None:
            try:
                detail = (exc.response.json().get("error") or {}).get("description") or detail
            except (ValueError, AttributeError):
                pass
        raise HTTPException(status_code=502 if status >= 500 else 400, detail=detail) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Could not reach Razorpay Test Mode API") from exc


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "merchantos", "version": "1.4.1"}


@router.get("/overview")
def overview():
    events = list_events()
    incidents = detect_incidents(events)
    learned_scores, model = learned_scores_for_events(events)
    clusters = cluster_summary(events, model_scores=learned_scores or None, model_threshold=model.get("threshold") or model.get("review_threshold")) if events else []
    actions = list_actions(limit=5000)
    approvals = list_approvals(limit=5000)
    failed = [e for e in events if e.event_type == "payment.failed"]
    captured = [e for e in events if e.event_type == "payment.captured"]
    return {
        "product": "MerchantOS AI — The AI Decision Layer for Autonomous Merchant Operations",
        "loop": ["OBSERVE", "UNDERSTAND", "SIMULATE", "DECIDE", "GUARD", "ACT", "VERIFY", "LEARN"],
        "data_source": "razorpay_test_mode_only",
        "payments": {"total": len(events), "failed": len(failed), "captured": len(captured)},
        "revenue": {
            "failed_value_inr": round(sum(e.amount for e in failed), 2),
            "verified_recovered_inr": round(sum(float(a.get("actual_recovery") or 0) for a in actions), 2),
        },
        "risknet": {"clusters": len(clusters), "high_risk_rings": sum(c.risk_level == "high" for c in clusters), "model": model_status()},
        "payguard": {"active_incidents": len(incidents), "revenue_at_risk_inr": round(sum(i.revenue_at_risk for i in incidents), 2)},
        "operations": {
            "decisions": len(list_decisions(limit=5000)),
            "pending_approvals": sum(a.get("status") == "PENDING" for a in approvals),
            "actions": len(actions),
        },
        "audit": verify_audit_chain(),
        "safety": {"live_mode": "blocked", "manual_payment_injection": "blocked", "test_actions_enabled": os.getenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "false")},
    }


@router.post("/events")
def ingest_event_disabled():
    raise HTTPException(status_code=403, detail="Manual event ingestion is disabled. Use Razorpay Test Mode Checkout, signed webhooks, or provider API verification.")


@router.get("/events")
def events():
    return [e.model_dump(mode="json") for e in list_events()]


@router.post("/decide")
def decide(request: DecisionRequest):
    event = get_event(request.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    try:
        return make_decision(event, auto_execute_test_action=request.auto_execute_test_action)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _current_clusters() -> list[RiskCluster]:
    current_events = list_events()
    if not current_events:
        return []
    scores, status = learned_scores_for_events(current_events)
    return cluster_summary(current_events, model_scores=scores or None, model_threshold=status.get("threshold") or status.get("review_threshold"))


@router.get("/clusters", response_model=list[RiskCluster])
def clusters(
    risk_level: Literal["high", "medium", "low"] | None = None,
    classification: Literal["HIGH_RISK_RING", "SUSPICIOUS_CLUSTER", "MONITOR", "BENIGN_SHARED_NETWORK"] | None = None,
):
    results = _current_clusters()
    if risk_level is not None:
        results = [c for c in results if c.risk_level == risk_level]
    if classification is not None:
        results = [c for c in results if c.classification == classification]
    return results


@router.get("/clusters/{cluster_id}", response_model=RiskCluster)
def cluster_detail(cluster_id: str):
    for cluster in _current_clusters():
        if cluster.cluster_id == cluster_id:
            return cluster
    raise HTTPException(status_code=404, detail="cluster not found")


@router.get("/decisions")
def decisions(limit: int = 100):
    return list_decisions(limit=max(1, min(limit, 500)))


@router.get("/payguard/status")
def payguard_status():
    current = detect_incidents(list_events())
    return {
        "mode": "Razorpay Test Mode payment degradation + root-cause evidence",
        "active_incidents": len(current),
        "incidents": [i.model_dump(mode="json") for i in current],
    }


@router.post("/payguard/analyze")
def payguard_analyze():
    incidents = detect_incidents(list_events())
    save_incidents(incidents)
    for incident in incidents:
        append_audit("incident", incident.incident_id, "payguard.incident_detected", incident.model_dump(mode="json"))
    return {"detected": len(incidents), "incidents": [i.model_dump(mode="json") for i in incidents]}


@router.get("/payguard/incidents")
def payguard_incidents(limit: int = 100):
    return list_incidents(limit=max(1, min(limit, 500)))


@router.get("/digital-twin/{event_id}")
def digital_twin(event_id: str):
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    all_events = list_events()
    risk = operational_risk_score(event, all_events)
    incidents = detect_incidents(all_events)
    incident = incident_for_event(event, incidents)
    rar = revenue_at_risk(event, all_events)
    options = simulate_interventions(event, all_events, risk_score=risk["risk_score"], revenue_at_risk=rar, incident=incident)
    return {
        "event_id": event_id,
        "risk": risk,
        "revenue_at_risk": rar,
        "payguard_incident": incident.model_dump(mode="json") if incident else None,
        "options": [o.model_dump(mode="json") for o in options],
        "note": "These are transparent Test Mode decision simulations, not guarantees of recovery.",
    }


@router.post("/orchestrator/run")
def orchestrator_run(body: OrchestratorRunRequest):
    return run_cycle(limit=body.limit, auto_execute_test_actions=body.auto_execute_test_actions, force_redecide=body.force_redecide)


@router.get("/approvals")
def approvals(limit: int = 100):
    return list_approvals(limit=max(1, min(limit, 500)))


@router.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: str, body: ApprovalDecisionRequest):
    approval = get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="approval not found")
    updated = decide_approval(approval_id, body.approved, body.note)
    action = None
    if body.approved and body.execute_if_approved:
        try:
            action = _provider_call(lambda: execute_payment_link_from_decision(approval["audit_id"], approved=True))
        except HTTPException:
            raise
        except (ValueError, PermissionError) as exc:
            return {"approval": updated, "action": None, "execution_note": str(exc)}
    append_audit("approval", approval_id, "approval.approved" if body.approved else "approval.rejected", {"note": body.note})
    return {"approval": updated, "action": action}


@router.get("/actions")
def actions(limit: int = 100):
    return list_actions(limit=max(1, min(limit, 500)))


@router.post("/actions/from-decision/{audit_id}")
def execute_from_decision(audit_id: str):
    decision = get_decision(audit_id)
    if not decision:
        raise HTTPException(status_code=404, detail="decision not found")
    approved = False
    if decision.get("approval_id"):
        approval = get_approval(decision["approval_id"])
        approved = bool(approval and approval.get("status") == "APPROVED")
    try:
        return _provider_call(lambda: execute_payment_link_from_decision(audit_id, approved=approved))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/actions/{action_id}/verify")
def verify_one_action(action_id: str):
    if not get_action(action_id):
        raise HTTPException(status_code=404, detail="action not found")
    return _provider_call(lambda: verify_action(action_id))


@router.post("/verify/run")
def verify_run():

    results = []
    errors = []

    checked = 0

    for action in list_actions(limit=500):

        if (
            action.get("provider_entity_type")
            != "payment_link"
        ):
            continue

        if action.get("status") in {
            "VERIFIED_RECOVERED",
            "VERIFIED_FAILED",
        }:
            continue

        checked += 1

        try:
            results.append(
                _provider_call(
                    lambda a=action:
                    verify_action(
                        a["action_id"]
                    )
                )
            )

        except HTTPException as exc:

            errors.append(
                {
                    "action_id":
                        action["action_id"],
                    "error":
                        exc.detail,
                }
            )

    recovered = sum(
        a.get("status")
        == "VERIFIED_RECOVERED"
        for a in results
    )

    partial = sum(
        a.get("status")
        == "VERIFIED_PARTIAL"
        for a in results
    )

    failed = sum(
        a.get("status")
        == "VERIFIED_FAILED"
        for a in results
    )

    pending = sum(
        a.get("status") in {
            "EXECUTED_TEST",
            "PENDING_VERIFICATION",
        }
        for a in results
    )

    return {
        "checked":
            checked,

        "verified":
            len(results),

        "recovered":
            recovered,

        "partial":
            partial,

        "failed":
            failed,

        "still_pending":
            pending,

        "errors_count":
            len(errors),

        "errors":
            errors,

        "actions":
            results,
    }


@router.get("/learning/status")
def get_learning_status():
    return learning_status()


@router.get("/ml/status")
def ml_status():
    all_events = list_events()
    model = model_status(all_events)
    return {
        "risk_graph": {
            "active_ml_model": bool(model.get("learned_calibrator_active")),
            "operational_model_active": bool(model.get("active", True)),
            "mode": model.get("model_type", "hybrid_policy_plus_bayesian_reputation"),
            "synthetic_model_active": False,
            "model": model,
            "training_readiness": dataset_readiness(all_events),
            "decision_agent_input": "risknet_hybrid_v2",
            "current_event_experiment_label_used_for_decision": False,
            "experiment_label_policy": "offline_training_and_evaluation_only",
            "action_allowed_directly_from_model": False,
        },
        "dataset": dataset_status(),
        "action_execution": "simulated_and_guarded",
        "bounded_test_mode_execution": "Payment Links only when explicitly enabled and guardrails pass",
    }


@router.get("/ml/risk-graph/status")
def risk_graph_status():
    model = model_status(list_events())
    return {
        **model,
        "data_source": "razorpay_test_mode_only",
        "synthetic_artifacts": "forbidden_as_active_inputs",
        "training_readiness": dataset_readiness(list_events()),
        "action_execution_directly_from_model": False,
    }


@router.post("/ml/risk-graph/train")
def train_risk_graph(body: RiskModelTrainRequest):
    # The finalized Buildathon artifact is locked. Refit requires an explicit
    # operator-controlled environment switch; merely calling the endpoint is
    # never enough to mutate the model.
    if os.getenv("MERCHANTOS_ALLOW_MODEL_REFIT", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=403,
            detail="RiskNet refit is locked. Set MERCHANTOS_ALLOW_MODEL_REFIT=true only for an intentional controlled refit.",
        )
    try:
        metrics = train_testmode_model(list_events(), activate=body.activate)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    append_audit("model", metrics["model_version"], "risknet.model_trained", {
        "data_source": metrics["data_source"], "validation": metrics["validation"], "test": metrics["test"]
    })
    return metrics


@router.get("/ml/risk-graph/stress-status")
def retired_synthetic_stress_status():
    return {"retired": True, "reason": "Synthetic stress artifacts are not active inputs in the Razorpay Test Mode-only product.", "replacement": "controlled Test Mode scenarios + chronological training/evaluation"}


def _feature_evidence(event_id: str) -> list[str]:
    event = get_event(event_id)
    if not event:
        return []
    prior = [e for e in list_events() if e.event_id != event_id and e.timestamp <= event.timestamp]
    evidence: list[str] = []
    for label, predicate in (
        ("other customers previously seen on this device", lambda e: e.device_id == event.device_id and event.device_id != "unknown"),
        ("other customers previously seen on this IP", lambda e: e.ip_address == event.ip_address and event.ip_address != "unknown"),
        ("other customers previously seen on this instrument", lambda e: e.instrument_id == event.instrument_id and event.instrument_id != "unknown"),
    ):
        customers = {e.customer_id for e in prior if predicate(e) and e.customer_id != event.customer_id}
        if customers:
            evidence.append(f"{label}: {len(customers)}")
    failed_neighbors = sum(
        e.event_type == "payment.failed" for e in prior
        if ((event.device_id != "unknown" and e.device_id == event.device_id) or (event.ip_address != "unknown" and e.ip_address == event.ip_address) or (event.instrument_id != "unknown" and e.instrument_id == event.instrument_id))
    )
    if failed_neighbors:
        evidence.append(f"prior failed payments on linked entities: {failed_neighbors}")
    return evidence[:8]


@router.get("/ml/risk-graph/score/{event_id}", response_model=RiskGraphScore)
def risk_graph_score(event_id: str):
    event = get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="event not found")
    as_of_events = [e for e in list_events() if e.timestamp <= event.timestamp]
    detail = operational_risk_score(event, as_of_events)
    threshold = detail["review_threshold"]
    return RiskGraphScore(
        event_id=event_id,
        risk_score=detail["risk_score"],
        review_threshold=threshold,
        critical_risk_threshold=detail.get("critical_risk_threshold"),
        flagged_for_review=detail["risk_score"] >= threshold,
        feature_evidence=_feature_evidence(event_id),
        scoring_mode=detail["scoring_mode"],
        active_ml_model=detail["active_ml_model"],
        action_allowed=False,
        deterministic_risk_score=detail["deterministic_risk_score"],
        learned_risk_score=detail["learned_risk_score"],
        model_version=detail["model_version"],
    )


@router.get("/audit")
def audit(limit: int = 200):
    return {"chain": verify_audit_chain(), "events": list_audit_events(limit=max(1, min(limit, 1000)))}


@router.get("/audit/verify")
def audit_verify():
    return verify_audit_chain()


@router.post("/journeys")
def create_payment_journey(body: PaymentJourneyCreateRequest):
    """Start a real Razorpay Test Mode payment and trace its operational lifetime.

    Live journeys are always UNLABELED. Controlled experiment labels remain
    offline training/evaluation metadata and cannot be supplied here.
    """
    client = _client()
    journey_id = f"jour-{uuid.uuid4().hex[:12]}"
    receipt = f"mosj-{uuid.uuid4().hex[:14]}"
    customer_hash = stable_hash(body.customer_ref or journey_id, "customer_ref")
    notes = {
        "merchantos_source": "test_mode",
        "merchantos_journey_id": journey_id,
        "merchantos_journey": "true",
        "merchantos_scenario": "UNLABELED",
    }
    order = _provider_call(lambda: client.create_order(body.amount_inr, receipt, notes=notes))
    # A Streamlit/Docker server request is not the customer's browser identity.
    # Store unknown device/IP instead of manufacturing graph evidence.
    save_order_context(
        order=order,
        scenario_label="UNLABELED",
        session_id=stable_hash(uuid.uuid4().hex, "session"),
        device_id="unknown",
        ip_address="unknown",
        customer_ref=customer_hash,
    )
    journey = save_journey(
        journey_id=journey_id,
        order_id=order["id"],
        amount=body.amount_inr,
        currency=str(order.get("currency") or "INR"),
        customer_ref=customer_hash,
        description=body.description or "MerchantOS live payment journey",
        metadata={"provider_order_status": order.get("status"), "provider_receipt": order.get("receipt")},
    )
    append_audit(
        "journey",
        journey_id,
        "journey.created",
        {"order_id": order["id"], "amount_inr": body.amount_inr, "scenario_label": "UNLABELED", "data_source": "razorpay_test_mode_only"},
    )
    return {
        "journey": journey,
        "test_mode": True,
        "scenario_label": "UNLABELED",
        "checkout_path": f"/journey-checkout/{journey_id}",
        "order": order,
    }


@router.get("/journeys")
def payment_journeys(limit: int = 50):
    items = []
    for journey in list_journeys(limit=max(1, min(limit, 200))):
        try:
            trace = project_journey(journey["journey_id"])
            items.append({
                **journey,
                "status": trace["status"],
                "payment_id": (trace.get("payment") or {}).get("payment_id"),
                "event_type": (trace.get("payment") or {}).get("event_type"),
                "risk_score": (trace.get("risk") or {}).get("risk_score"),
                "guardrail_status": (trace.get("decision") or {}).get("guardrail_status"),
                "actual_recovery": sum(float(a.get("actual_recovery") or 0) for a in trace.get("actions") or []),
            })
        except ValueError:
            items.append(journey)
    return {"items": items, "count": len(items), "data_source": "razorpay_test_mode_only"}


@router.get("/journeys/{journey_id}")
def payment_journey(journey_id: str):
    try:
        return project_journey(journey_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/journeys/{journey_id}/checkout-opened")
def journey_checkout_opened(journey_id: str):
    if not get_journey(journey_id):
        raise HTTPException(status_code=404, detail="journey not found")
    append_audit("journey", journey_id, "journey.checkout_opened", {"environment": "razorpay_test_mode"})
    update_journey(journey_id, status="CHECKOUT_OPEN")
    return {"status": "recorded", "journey_id": journey_id}


@router.post("/journeys/{journey_id}/refresh")
def refresh_payment_journey(journey_id: str):
    journey = get_journey(journey_id)
    if not journey:
        raise HTTPException(status_code=404, detail="journey not found")
    client = _client()
    order = _provider_call(lambda: client.fetch_order(journey["order_id"]))
    collection = _provider_call(lambda: client.fetch_order_payments(journey["order_id"]))
    synced: list[str] = []
    for payment in collection.get("items", []):
        synced.append(_sync_one_payment(payment, "razorpay_test_mode_api_sync").event_id)
    metadata = dict(journey.get("metadata") or {})
    metadata.update({"provider_order_status": order.get("status"), "last_provider_refresh_at": datetime.now(timezone.utc).isoformat()})
    update_journey(journey_id, metadata=metadata)
    append_audit("journey", journey_id, "journey.provider_refreshed", {"order_id": journey["order_id"], "payments_synced": len(synced), "event_ids": synced})
    return project_journey(journey_id)


@router.post("/journeys/{journey_id}/analyze")
def analyze_payment_journey(journey_id: str, body: JourneyAnalyzeRequest):
    if not get_journey(journey_id):
        raise HTTPException(status_code=404, detail="journey not found")
    try:
        return analyze_journey(
            journey_id,
            auto_execute_test_action=body.auto_execute_test_action,
            force_redecide=body.force_redecide,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/journeys/{journey_id}/verify")
def verify_payment_journey(journey_id: str):
    if not get_journey(journey_id):
        raise HTTPException(status_code=404, detail="journey not found")
    try:
        return _provider_call(lambda: verify_journey(journey_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/razorpay/status")
def razorpay_status():
    client = _client()
    return {
        "configured": client.configured,
        "has_credentials": client.has_credentials,
        "test_mode_key": client.is_test_mode,
        "key_id_prefix": client.key_id[:12] + "..." if client.key_id else None,
        "webhook_secret_configured": bool(os.getenv("RAZORPAY_WEBHOOK_SECRET")),
        "data_source": "razorpay_test_mode_only",
        "manual_event_ingestion": "disabled",
        "synthetic_generators": "not_part_of_active_v1_build",
        "ingestion_policy": {"primary_observation": "signed_webhook", "api_role": "verification_and_backfill", "webhook_provenance_is_sticky": True},
        "bounded_test_actions": {"enabled": os.getenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "false"), "provider_action": "Payment Links only"},
        "webhooks": webhook_stats(),
    }


@router.post("/razorpay/orders")
def create_razorpay_order(body: RazorpayOrderCreateRequest, request: Request):
    client = _client()
    receipt = body.receipt or f"mos-{uuid.uuid4().hex[:16]}"
    client_ip = request.client.host if request.client else "unknown"
    session_hash = stable_hash(body.session_id or uuid.uuid4().hex, "session")
    device_hash = stable_hash(body.device_id, "device")
    ip_hash = stable_hash(client_ip, "ip")
    customer_hash = stable_hash(body.customer_ref, "customer_ref")
    notes = {"merchantos_source": "test_mode", "merchantos_scenario": body.scenario_label, "merchantos_session": session_hash, **{str(k)[:40]: str(v)[:200] for k, v in list(body.notes.items())[:8]}}
    order = _provider_call(lambda: client.create_order(body.amount_inr, receipt, notes=notes))
    save_order_context(order=order, scenario_label=body.scenario_label, session_id=session_hash, device_id=device_hash, ip_address=ip_hash, customer_ref=customer_hash)
    append_audit("order", order["id"], "razorpay.test_order_created", {"amount_inr": body.amount_inr, "scenario_label": body.scenario_label})
    return {"test_mode": True, "key_id": client.key_id, "order": order, "scenario_label": body.scenario_label, "context": {"session_id": session_hash, "device_id": device_hash, "ip_address": ip_hash}}


@router.get("/razorpay/orders")
def fetch_razorpay_orders(count: int = 100, skip: int = 0):
    return _provider_call(lambda: _client().fetch_orders(count=max(1, min(count, 100)), skip=max(0, skip)))


@router.get("/razorpay/payments")
def fetch_razorpay_payments(count: int = 100, skip: int = 0):
    return _provider_call(lambda: _client().fetch_payments(count=max(1, min(count, 100)), skip=max(0, skip)))


@router.get("/razorpay/local-orders")
def local_razorpay_orders(limit: int = 100):
    return list_order_contexts(limit=max(1, min(limit, 500)))


@router.get("/razorpay/dataset-status")
def razorpay_dataset_status():
    return {**dataset_status(), "risknet_training_readiness": dataset_readiness(list_events())}


@router.get("/razorpay/webhooks")
def razorpay_webhook_history(limit: int = 100):
    return {"policy": "webhook_primary_api_verification", "stats": webhook_stats(), "items": list_webhook_events(limit=max(1, min(limit, 500)))}


def _sync_one_payment(payment: dict, source: str):
    context = get_order_context(payment.get("order_id")) or {}
    event = normalize_payment_entity(payment, context=context, source=source)
    stored = upsert_event(event)
    append_audit("payment", stored.event_id, "payment.api_verified" if source.endswith("api_sync") else "payment.webhook_observed", {"event_type": stored.event_type, "payment_id": stored.payment_id, "source": stored.source})
    return stored


@router.post("/razorpay/payments/{payment_id}/sync")
def sync_payment(payment_id: str):
    if not payment_id.startswith("pay_"):
        raise HTTPException(status_code=400, detail="invalid Razorpay payment id")
    payment = _provider_call(lambda: _client().fetch_payment(payment_id))
    event = _sync_one_payment(payment, "razorpay_test_mode_api_sync")
    return {"status": "verified", "event": event.model_dump(mode="json")}


@router.post("/razorpay/sync")
def sync_razorpay_payments(body: RazorpaySyncRequest):
    collection = _provider_call(lambda: _client().fetch_payments(count=body.count, skip=body.skip))
    synced, errors = [], []
    for payment in collection.get("items", []):
        try:
            synced.append(_sync_one_payment(payment, "razorpay_test_mode_api_sync").event_id)
        except (ValueError, TypeError) as exc:
            errors.append({"payment_id": payment.get("id"), "error": str(exc)})
    return {"status": "complete", "fetched": len(collection.get("items", [])), "synced": len(synced), "event_ids": synced, "errors": errors}


@router.post("/razorpay/purge-legacy-local-events")
def purge_legacy_local_events():
    removed = clear_non_razorpay_events()
    return {"removed": removed, "remaining_test_mode_events": len(list_events())}


@router.post("/razorpay/webhook")
async def razorpay_webhook(request: Request, x_razorpay_signature: str | None = Header(default=None), x_razorpay_event_id: str | None = Header(default=None)):
    secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "").strip()
    body = await request.body()
    if not secret:
        raise HTTPException(status_code=503, detail="webhook secret not configured")
    if not x_razorpay_signature:
        raise HTTPException(status_code=401, detail="missing webhook signature")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_razorpay_signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="invalid webhook JSON") from exc

    event_type = str(payload.get("event") or "unknown")
    payload_hash = hashlib.sha256(body).hexdigest()
    webhook_event_id = x_razorpay_event_id or f"sha256:{payload_hash}"
    if not claim_webhook_event(webhook_event_id, event_type, payload_hash):
        return {"status": "duplicate_ignored", "webhook_event_id": webhook_event_id}

    normalized_event_id = None
    try:
        payment = payment_from_webhook(payload)
        if payment and (event_type.startswith("payment.") or event_type.startswith("payment_link.")):
            context = get_order_context(payment.get("order_id")) or {}
            event = normalize_payment_entity(payment, context=context, source="razorpay_test_mode_webhook", webhook_event=event_type if event_type.startswith("payment.") else None)
            stored_event = upsert_event(event)
            normalized_event_id = stored_event.event_id
            append_audit("payment", stored_event.event_id, "payment.webhook_observed", {"webhook_event_id": webhook_event_id, "event_type": event_type, "payment_id": stored_event.payment_id})

        payment_link = payment_link_from_webhook(payload)
        if payment_link and event_type.startswith("payment_link."):
            update_action_from_payment_link_webhook(payment_link, event_type)

        mark_webhook_processed(webhook_event_id, normalized_event_id=normalized_event_id)
    except Exception as exc:
        mark_webhook_processed(webhook_event_id, normalized_event_id=normalized_event_id, processing_error=str(exc))
        raise HTTPException(status_code=500, detail="webhook processing failed") from exc
    return {"status": "verified_and_processed", "webhook_event_id": webhook_event_id, "event_type": event_type, "normalized_event_id": normalized_event_id}


init_db()
