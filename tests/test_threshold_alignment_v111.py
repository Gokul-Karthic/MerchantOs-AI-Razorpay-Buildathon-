from app.ml.risk_model import _runtime_thresholds
from app.services.guardrails import evaluate_guardrails
from app.models.schemas import PaymentEvent
from datetime import datetime, timezone


def test_v11_manifest_migrates_validated_threshold():
    manifest = {
        "review_threshold": 0.85,
        "holdout": {"threshold": 0.64},
    }
    review, critical = _runtime_thresholds(manifest)
    assert review == 0.64
    assert critical == 0.85


def test_guardrail_blocks_at_validated_review_threshold(monkeypatch):
    event = PaymentEvent(
        event_id="rzp-payment:pay_test",
        event_type="payment.failed",
        order_id="order_test",
        payment_id="pay_test",
        customer_id="customer_test",
        amount=499.0,
        currency="INR",
        method="card",
        bank="unknown",
        device_id="device_test",
        ip_address="ip_test",
        instrument_id="unknown",
        merchant_id="merchant-test",
        timestamp=datetime.now(timezone.utc),
        source="razorpay_test_mode_webhook",
        scenario_label="NORMAL",
        metadata={},
    )
    result = evaluate_guardrails(event, risk_score=0.64, action="payment_link", review_threshold=0.64)
    assert result.status == "BLOCKED"
    assert result.provider_action_allowed is False


def test_controlled_experiment_label_does_not_block_low_risk_simulation():
    """Ground-truth experiment labels must never leak into live guardrails."""
    event = PaymentEvent(
        event_id="rzp-payment:pay_label_leak",
        event_type="payment.failed",
        order_id="order_label_leak",
        payment_id="pay_label_leak",
        customer_id="customer_label_leak",
        amount=499.0,
        currency="INR",
        method="card",
        bank="unknown",
        device_id="device_test",
        ip_address="ip_test",
        instrument_id="unknown",
        merchant_id="merchant-test",
        timestamp=datetime.now(timezone.utc),
        source="razorpay_test_mode_webhook",
        scenario_label="CONTROLLED_ABUSE",
        metadata={},
    )
    result = evaluate_guardrails(
        event,
        risk_score=0.18,
        action="alternate_method",
        review_threshold=0.64,
    )
    assert result.status == "SIMULATION_ONLY"
    assert "review threshold reached" not in result.reason.lower()


def test_action_selection_uses_risk_not_ground_truth_label():
    from types import SimpleNamespace
    from app.agents.decision_agent import _choose_action

    event = PaymentEvent(
        event_id="rzp-payment:pay_action_label_leak",
        event_type="payment.failed",
        order_id="order_action_label_leak",
        payment_id="pay_action_label_leak",
        customer_id="customer_action_label_leak",
        amount=499.0,
        currency="INR",
        method="card",
        bank="unknown",
        device_id="device_test",
        ip_address="ip_test",
        instrument_id="unknown",
        merchant_id="merchant-test",
        timestamp=datetime.now(timezone.utc),
        source="razorpay_test_mode_webhook",
        scenario_label="CONTROLLED_ABUSE",
        metadata={},
    )
    options = [
        SimpleNamespace(action="payment_link", expected_net_value_inr=100.0),
        SimpleNamespace(action="alternate_method", expected_net_value_inr=90.0),
        SimpleNamespace(action="escalate_review", expected_net_value_inr=-25.0),
    ]
    action, reason = _choose_action(event, 0.18, options, None, 0.64)
    assert action == "payment_link"
    assert "threshold" not in reason.lower()
