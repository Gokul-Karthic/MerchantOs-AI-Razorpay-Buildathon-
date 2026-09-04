from datetime import datetime, timedelta, timezone

import numpy as np

from app.ml.risk_hybrid_features import identity_quality
from app.ml.risk_model import _quality_gate
from app.models.schemas import PaymentEvent


def test_collapsed_local_identity_is_suppressed():
    base = datetime(2026, 8, 30, tzinfo=timezone.utc)
    events = [
        PaymentEvent(
            event_id=f"rzp-payment:pay_Q{i}", event_type="payment.failed", order_id=f"order_Q{i}",
            payment_id=f"pay_Q{i}", customer_id=f"cust-{i}", amount=499, method="netbanking", bank="BARB_R",
            device_id="device-one", ip_address="ip-one", instrument_id="unknown",
            source="razorpay_test_mode_webhook", scenario_label="CONTROLLED_ABUSE" if i % 4 == 0 else "NORMAL",
            timestamp=base + timedelta(minutes=i),
        ) for i in range(20)
    ]
    q = identity_quality(events)
    assert q["unique_devices"] == 1
    assert q["unique_ips"] == 1
    assert q["device_features_allowed"] is False
    assert q["ip_features_allowed"] is False


def test_degenerate_all_positive_candidate_fails_quality_gate():
    metrics = {
        "confusion_matrix": [[0, 13], [0, 3]],
        "roc_auc": 0.20,
        "pr_auc_lift_vs_baseline": 0.8,
        "precision": 0.1875,
        "recall": 1.0,
        "predicted_positive_rate": 1.0,
    }
    passed, reasons = _quality_gate(metrics)
    assert passed is False
    assert reasons


def test_training_endpoint_respects_locked_refit_switch(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.services import store

    monkeypatch.setattr(store, "DB_PATH", tmp_path / "locked-train.db")
    store.init_db()
    monkeypatch.setenv("MERCHANTOS_ALLOW_MODEL_REFIT", "false")
    with TestClient(app) as client:
        response = client.post("/api/ml/risk-graph/train", json={"activate": True})
    assert response.status_code == 403
    assert "refit is locked" in response.json()["detail"].lower()
