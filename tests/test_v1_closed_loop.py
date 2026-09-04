from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.agents.decision_agent import make_decision
from app.main import app
from app.ml.payguard import detect_incidents
from app.ml.risk_model import dataset_readiness
from app.models.schemas import PaymentEvent
from app.services import store
from app.services.razorpay_client import RazorpayClient


def _fresh_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "merchantos-v1-test.db")
    store.init_db()


def _event(i: int, *, amount=499.0, failed=True, scenario="NORMAL", customer=None, device=None, ip=None, instrument=None, method="netbanking", bank="BARB_R"):
    return PaymentEvent(
        event_id=f"rzp-payment:pay_V1{i}",
        event_type="payment.failed" if failed else "payment.captured",
        order_id=f"order_V1{i}",
        payment_id=f"pay_V1{i}",
        customer_id=customer or f"customer-{i}",
        amount=amount,
        method=method,
        bank=bank,
        device_id=device or f"device-{i}",
        ip_address=ip or f"ip-{i}",
        instrument_id=instrument or "unknown",
        source="razorpay_test_mode_webhook",
        scenario_label=scenario,
        timestamp=datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc) + timedelta(minutes=i * 5),
        metadata={"error_reason": "payment_failed", "error_source": "bank", "error_step": "payment_authorization"} if failed else {},
    )


def test_payguard_detects_real_testmode_degradation():
    events = [_event(i) for i in range(5)]
    incidents = detect_incidents(events)
    assert len(incidents) == 1
    assert incidents[0].method == "netbanking"
    assert incidents[0].recent_failure_rate == 1.0
    assert incidents[0].revenue_at_risk > 0
    assert "error source bank" in incidents[0].root_cause


def test_high_risk_event_is_never_auto_recovered(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    event = _event(6, scenario="CONTROLLED_ABUSE")
    store.upsert_event(event)

    # Runtime safety must be driven by RiskNet output, never by the offline label.
    monkeypatch.setattr(
        "app.agents.decision_agent.score_event",
        lambda event, events: {
            "risk_score": 0.80,
            "review_threshold": 0.64,
            "learned_risk_score": 0.90,
            "deterministic_risk_score": 0.70,
        },
    )
    decision = make_decision(event)
    assert decision.recommended_action == "escalate_review"
    assert decision.guardrail_status == "BLOCKED"
    assert decision.action_id is None


def test_low_risk_test_payment_link_can_execute_when_explicitly_enabled(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_v1")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "true")
    event = _event(1, amount=499.0)
    store.upsert_event(event)

    def fake_create(self, **kwargs):
        return {"id": "plink_V1", "status": "issued", "amount": 49900, "amount_paid": 0, "short_url": "https://rzp.io/i/test"}
    monkeypatch.setattr(RazorpayClient, "create_payment_link", fake_create)

    decision = make_decision(event, auto_execute_test_action=True)
    assert decision.recommended_action == "payment_link"
    assert decision.guardrail_status == "AUTO_ALLOWED_TEST"
    assert decision.action_id is not None
    action = store.get_action(decision.action_id)
    assert action["execution_mode"] == "razorpay_test_mode"
    assert action["provider_entity_id"] == "plink_V1"
    assert action["expected_recovery"] == decision.simulation["payment_link"]
    assert store.verify_audit_chain()["valid"] is True


def test_high_value_payment_link_requires_approval(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_v1")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "true")
    event = _event(2, amount=5000.0)
    store.upsert_event(event)
    decision = make_decision(event)
    assert decision.recommended_action == "payment_link"
    assert decision.guardrail_status == "APPROVAL_REQUIRED"
    assert decision.approval_id is not None
    assert store.get_approval(decision.approval_id)["status"] == "PENDING"


def test_risknet_training_gate_never_uses_unlabeled_or_synthetic_rows():
    events = [_event(i, scenario="NORMAL") for i in range(10)] + [_event(20, scenario="UNLABELED")]
    readiness = dataset_readiness(events)
    assert readiness["ready"] is False
    assert readiness["counts"]["labeled"] == 10
    assert readiness["checks"]["test_mode_only"] is True


def test_orchestrator_is_idempotent_for_existing_decisions(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    for i in range(3):
        store.upsert_event(_event(i))
    with TestClient(app) as client:
        first = client.post("/api/orchestrator/run", json={"limit": 10}).json()
        second = client.post("/api/orchestrator/run", json={"limit": 10}).json()
    assert first["new_decisions"] == 3
    assert second["new_decisions"] == 0
    assert second["skipped_existing_decisions"] == 3


def test_v1_overview_exposes_complete_closed_loop(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    store.upsert_event(_event(1))
    with TestClient(app) as client:
        response = client.get("/api/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["loop"] == ["OBSERVE", "UNDERSTAND", "SIMULATE", "DECIDE", "GUARD", "ACT", "VERIFY", "LEARN"]
    assert data["data_source"] == "razorpay_test_mode_only"
    assert data["safety"]["live_mode"] == "blocked"


def test_payment_link_webhook_closes_action_loop(monkeypatch, tmp_path):
    import hashlib, hmac, json
    _fresh_db(monkeypatch, tmp_path)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "wh-v1")
    event = _event(30)
    store.upsert_event(event)
    store.save_action({
        "action_id": "act-webhook-v1", "audit_id": "dec-webhook-v1", "event_id": event.event_id,
        "action_type": "payment_link", "execution_mode": "razorpay_test_mode", "status": "EXECUTED_TEST",
        "provider_entity_type": "payment_link", "provider_entity_id": "plink_WEBHOOK_V1",
        "provider_payload": {}, "expected_recovery": 300, "actual_recovery": 0,
        "created_at": datetime.now(timezone.utc).isoformat(), "executed_at": datetime.now(timezone.utc).isoformat(),
        "verified_at": None,
    })
    payload = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": "plink_WEBHOOK_V1", "status": "paid", "amount": 49900, "amount_paid": 49900}},
            "payment": {"entity": {"id": "pay_RECOVERY_V1", "order_id": "order_RECOVERY_V1", "amount": 49900, "currency": "INR", "status": "captured", "method": "upi", "created_at": 1788027000}},
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(b"wh-v1", body, hashlib.sha256).hexdigest()
    with TestClient(app) as client:
        response = client.post("/api/razorpay/webhook", content=body, headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt-pl-v1"})
    assert response.status_code == 200
    action = store.get_action("act-webhook-v1")
    assert action["status"] == "VERIFIED_RECOVERED"
    assert action["actual_recovery"] == 499.0
    assert store.get_event("rzp-payment:pay_RECOVERY_V1") is not None


def test_testmode_model_training_pipeline_is_data_source_gated(monkeypatch, tmp_path):
    from app.ml import risk_model
    _fresh_db(monkeypatch, tmp_path)
    monkeypatch.setattr(risk_model, "MODEL_PATH", tmp_path / "risk.joblib")
    monkeypatch.setattr(risk_model, "METRICS_PATH", tmp_path / "metrics.json")
    base = datetime(2026, 8, 29, 8, 0, tzinfo=timezone.utc)
    events = []
    for i in range(60):
        abuse = i % 3 == 0
        events.append(PaymentEvent(
            event_id=f"rzp-payment:pay_TRAIN_{i}", event_type="payment.failed" if abuse else "payment.captured",
            order_id=f"order_TRAIN_{i}", payment_id=f"pay_TRAIN_{i}", customer_id=f"cust-{i%15}", amount=100+i,
            method="card" if i % 2 == 0 else "upi", bank="unknown",
            device_id="dev-abuse" if abuse else f"dev-{i%12}", ip_address="ip-abuse" if abuse else f"ip-{i%10}",
            instrument_id="card-abuse" if abuse else f"inst-{i%20}", source="razorpay_test_mode_webhook",
            scenario_label="CONTROLLED_ABUSE" if abuse else "NORMAL", timestamp=base + timedelta(minutes=i*3),
        ))
    assert risk_model.dataset_readiness(events)["ready"] is True
    metrics = risk_model.train_testmode_model(events, activate=True)
    assert metrics["data_source"] == "razorpay_test_mode_only"
    assert metrics["active"] is True
    assert metrics["validation"]["threshold"] > 0
