from __future__ import annotations

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.main import app
from app.services import store
from app.services.razorpay_client import RazorpayClient
from app.services.razorpay_ingestion import normalize_payment_entity


def _fresh_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "merchantos-test.db")
    store.init_db()


def test_client_rejects_live_key(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_live_do_not_use")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    client = RazorpayClient()
    assert client.configured is False
    try:
        client.fetch_payments()
        assert False, "live key should be rejected"
    except RuntimeError as exc:
        assert "refuses non-Test" in str(exc)


def test_normalizer_uses_only_razorpay_payment_and_local_test_context():
    payment = {
        "id": "pay_TEST123",
        "order_id": "order_TEST123",
        "amount": 49900,
        "currency": "INR",
        "status": "failed",
        "method": "card",
        "card_id": "card_TEST",
        "created_at": 1760000000,
        "error_reason": "incorrect_otp",
    }
    context = {
        "device_id": "device_hash",
        "ip_address": "ip_hash",
        "scenario_label": "CONTROLLED_ABUSE",
        "merchant_id": "merchant-test",
    }
    event = normalize_payment_entity(payment, context=context, source="razorpay_test_mode_api_sync")
    assert event.payment_id == "pay_TEST123"
    assert event.order_id == "order_TEST123"
    assert event.amount == 499.0
    assert event.instrument_id == "card_TEST"
    assert event.source == "razorpay_test_mode_api_sync"
    assert event.scenario_label == "CONTROLLED_ABUSE"
    assert event.metadata["error_reason"] == "incorrect_otp"


def test_manual_event_ingestion_is_disabled():
    with TestClient(app) as client:
        response = client.post("/api/events", json={})
    assert response.status_code == 403


def test_test_checkout_page_exists():
    with TestClient(app) as client:
        response = client.get("/test-checkout")
    assert response.status_code == 200
    assert "checkout.razorpay.com" in response.text
    assert "No local synthetic payment generator" in response.text


def test_webhook_signature_normalizes_and_is_idempotent(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    secret = "whsec-test"
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", secret)

    order = {
        "id": "order_WEBHOOK1",
        "amount": 49900,
        "currency": "INR",
        "receipt": "mos-webhook",
        "status": "created",
    }
    store.save_order_context(
        order=order,
        scenario_label="NORMAL",
        session_id="session_hash",
        device_id="device_hash",
        ip_address="ip_hash",
        customer_ref="customer_hash",
    )

    payload = {
        "event": "payment.failed",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_WEBHOOK1",
                    "order_id": "order_WEBHOOK1",
                    "amount": 49900,
                    "currency": "INR",
                    "status": "failed",
                    "method": "upi",
                    "vpa": "failure@razorpay",
                    "created_at": 1760000000,
                    "error_reason": "payment_failed",
                }
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_webhook_1", "Content-Type": "application/json"}

    with TestClient(app) as client:
        first = client.post("/api/razorpay/webhook", content=body, headers=headers)
        second = client.post("/api/razorpay/webhook", content=body, headers=headers)

    assert first.status_code == 200
    assert first.json()["normalized_event_id"] == "rzp-payment:pay_WEBHOOK1"
    assert second.json()["status"] == "duplicate_ignored"
    event = store.get_event("rzp-payment:pay_WEBHOOK1")
    assert event is not None
    assert event.source == "razorpay_test_mode_webhook"
    assert event.device_id == "device_hash"
    assert event.scenario_label == "NORMAL"


def test_invalid_webhook_signature_is_rejected(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", "secret")
    with TestClient(app) as client:
        response = client.post(
            "/api/razorpay/webhook",
            content=b'{"event":"payment.failed"}',
            headers={"X-Razorpay-Signature": "bad"},
        )
    assert response.status_code == 401


def test_status_declares_testmode_only(monkeypatch):
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_123456789")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    with TestClient(app) as client:
        response = client.get("/api/razorpay/status")
    data = response.json()
    assert data["test_mode_key"] is True
    assert data["data_source"] == "razorpay_test_mode_only"
    assert data["manual_event_ingestion"] == "disabled"


def test_ml_status_does_not_activate_synthetic_model(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    with TestClient(app) as client:
        response = client.get("/api/ml/status")
    data = response.json()
    assert data["risk_graph"]["synthetic_model_active"] is False
    if data["risk_graph"]["active_ml_model"]:
        assert data["risk_graph"]["model"]["data_source"] == "razorpay_test_mode_only"
    assert data["action_execution"] == "simulated_and_guarded"


def test_feature_labels_come_from_controlled_testmode_scenario_only():
    from datetime import datetime, timezone
    from app.ml.risk_graph_features import temporal_graph_features
    from app.models.schemas import PaymentEvent

    rows = [
        PaymentEvent(event_id="rzp-payment:pay_A", event_type="payment.captured", order_id="order_A", payment_id="pay_A", customer_id="cA", amount=100, source="razorpay_test_mode_api_sync", scenario_label="NORMAL", timestamp=datetime(2026,1,1,tzinfo=timezone.utc)),
        PaymentEvent(event_id="rzp-payment:pay_B", event_type="payment.failed", order_id="order_B", payment_id="pay_B", customer_id="cB", amount=100, source="razorpay_test_mode_api_sync", scenario_label="CONTROLLED_ABUSE", timestamp=datetime(2026,1,2,tzinfo=timezone.utc)),
        PaymentEvent(event_id="rzp-payment:pay_C", event_type="payment.captured", order_id="order_C", payment_id="pay_C", customer_id="cC", amount=100, source="razorpay_test_mode_api_sync", scenario_label="UNLABELED", timestamp=datetime(2026,1,3,tzinfo=timezone.utc)),
    ]
    frame = temporal_graph_features(rows).set_index("event_id")
    assert frame.loc["rzp-payment:pay_A", "label"] == 0
    assert frame.loc["rzp-payment:pay_B", "label"] == 1
    assert frame.loc["rzp-payment:pay_C", "label"] == -1


def test_webhook_provenance_is_sticky_after_api_verification(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from app.models.schemas import PaymentEvent

    _fresh_db(monkeypatch, tmp_path)
    base = dict(
        event_id="rzp-payment:pay_PROVENANCE",
        order_id="order_PROVENANCE",
        payment_id="pay_PROVENANCE",
        customer_id="customer_hash",
        amount=499.0,
        currency="INR",
        method="card",
        bank="unknown",
        device_id="device_hash",
        ip_address="ip_hash",
        instrument_id="card_TEST",
        merchant_id="merchant-test",
        timestamp=datetime(2026, 8, 29, tzinfo=timezone.utc),
        scenario_label="CONTROLLED_ABUSE",
    )
    webhook_event = PaymentEvent(
        **base,
        event_type="payment.failed",
        source="razorpay_test_mode_webhook",
        metadata={"provider_status": "failed", "error_reason": "payment_failed"},
    )
    first = store.upsert_event(webhook_event)
    assert first.source == "razorpay_test_mode_webhook"
    assert first.metadata["webhook_verified"] is True

    api_event = PaymentEvent(
        **{**base, "scenario_label": "UNLABELED"},
        event_type="payment.failed",
        source="razorpay_test_mode_api_sync",
        metadata={"provider_status": "failed"},
    )
    second = store.upsert_event(api_event)
    assert second.source == "razorpay_test_mode_webhook"
    assert second.scenario_label == "CONTROLLED_ABUSE"
    assert second.metadata["webhook_verified"] is True
    assert second.metadata["api_verified"] is True
    assert second.metadata["primary_ingestion_source"] == "razorpay_test_mode_webhook"
    assert set(second.metadata["ingestion_sources"]) == {
        "razorpay_test_mode_webhook",
        "razorpay_test_mode_api_sync",
    }


def test_webhook_upgrades_api_sync_and_late_authorized_does_not_downgrade(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from app.models.schemas import PaymentEvent

    _fresh_db(monkeypatch, tmp_path)
    common = dict(
        event_id="rzp-payment:pay_ORDERING",
        order_id="order_ORDERING",
        payment_id="pay_ORDERING",
        customer_id="customer_hash",
        amount=100.0,
        currency="INR",
        method="card",
        bank="unknown",
        device_id="device_hash",
        ip_address="ip_hash",
        instrument_id="card_TEST",
        merchant_id="merchant-test",
        timestamp=datetime(2026, 8, 29, tzinfo=timezone.utc),
        scenario_label="NORMAL",
    )
    api_captured = PaymentEvent(
        **common,
        event_type="payment.captured",
        source="razorpay_test_mode_api_sync",
        metadata={"provider_status": "captured"},
    )
    store.upsert_event(api_captured)

    late_authorized_webhook = PaymentEvent(
        **common,
        event_type="payment.authorized",
        source="razorpay_test_mode_webhook",
        metadata={"provider_status": "authorized"},
    )
    merged = store.upsert_event(late_authorized_webhook)
    assert merged.source == "razorpay_test_mode_webhook"
    assert merged.event_type == "payment.captured"
    assert merged.metadata["provider_status"] == "captured"
    assert merged.metadata["last_webhook_event_type"] == "payment.authorized"


def test_webhook_history_endpoint(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    assert store.claim_webhook_event("evt_history_1", "payment.failed", "abc123") is True
    store.mark_webhook_processed(
        "evt_history_1",
        normalized_event_id="rzp-payment:pay_HISTORY",
    )
    with TestClient(app) as client:
        response = client.get("/api/razorpay/webhooks?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["policy"] == "webhook_primary_api_verification"
    assert data["stats"] == {"total": 1, "processed": 1}
    assert data["items"][0]["normalized_event_id"] == "rzp-payment:pay_HISTORY"
