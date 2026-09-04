from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.services import store


class FakeRazorpay:
    key_id = "rzp_test_fake"
    configured = True
    has_credentials = True
    is_test_mode = True

    def __init__(self):
        self.order = {
            "id": "order_JOURNEY1",
            "amount": 49900,
            "currency": "INR",
            "receipt": "mosj-test",
            "status": "created",
        }
        self.payments: list[dict] = []

    def create_order(self, amount_inr, receipt, notes=None):
        self.order = {**self.order, "amount": int(round(amount_inr * 100)), "receipt": receipt, "notes": notes or {}}
        return self.order

    def fetch_order(self, order_id):
        assert order_id == self.order["id"]
        return self.order

    def fetch_order_payments(self, order_id):
        assert order_id == self.order["id"]
        return {"items": self.payments}


def _fresh_db(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "journey-test.db")
    store.init_db()


def test_live_journey_is_real_testmode_and_unlabeled(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    fake = FakeRazorpay()
    monkeypatch.setattr(routes, "_client", lambda: fake)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    with TestClient(app) as client:
        created = client.post("/api/journeys", json={"amount_inr": 499, "customer_ref": "demo-01"})
        assert created.status_code == 200
        payload = created.json()
        jid = payload["journey"]["journey_id"]
        assert payload["scenario_label"] == "UNLABELED"
        assert payload["test_mode"] is True
        assert payload["order"]["id"] == "order_JOURNEY1"

        trace = client.get(f"/api/journeys/{jid}")
        assert trace.status_code == 200
        body = trace.json()
        assert body["status"] == "AWAITING_PAYMENT"
        assert body["safety"]["synthetic_payment_created"] is False
        assert body["safety"]["scenario_label"] == "UNLABELED"
        assert body["safety"]["live_mode_allowed"] is False

        checkout = client.get(f"/journey-checkout/{jid}")
        assert checkout.status_code == 200
        assert "checkout.razorpay.com" in checkout.text
        assert "No synthetic payment row is created" in checkout.text


def test_live_journey_refresh_projects_failed_payment_and_decision(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    fake = FakeRazorpay()
    monkeypatch.setattr(routes, "_client", lambda: fake)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")
    monkeypatch.setenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "false")

    with TestClient(app) as client:
        created = client.post("/api/journeys", json={"amount_inr": 499}).json()
        jid = created["journey"]["journey_id"]
        fake.payments = [{
            "id": "pay_JOURNEY1",
            "order_id": "order_JOURNEY1",
            "amount": 49900,
            "currency": "INR",
            "status": "failed",
            "method": "netbanking",
            "bank": "BARB_R",
            "created_at": 1788100000,
            "error_reason": "payment_failed",
        }]

        refreshed = client.post(f"/api/journeys/{jid}/refresh")
        assert refreshed.status_code == 200
        body = refreshed.json()
        assert body["status"] == "FAILED"
        assert body["payment"]["payment_id"] == "pay_JOURNEY1"
        assert body["payment"]["scenario_label"] == "UNLABELED"
        assert body["risk"] is not None
        assert body["digital_twin"]

        analyzed = client.post(
            f"/api/journeys/{jid}/analyze",
            json={"auto_execute_test_action": False, "force_redecide": False},
        )
        assert analyzed.status_code == 200
        result = analyzed.json()
        assert result["decision"] is not None
        assert result["decision"]["event_id"] == "rzp-payment:pay_JOURNEY1"
        stages = {item["stage"] for item in result["timeline"]}
        assert {"OBSERVE", "UNDERSTAND", "SIMULATE", "DECIDE", "GUARD"}.issubset(stages)


def test_successful_live_journey_analysis_is_a_safe_noop(monkeypatch, tmp_path):
    _fresh_db(monkeypatch, tmp_path)
    fake = FakeRazorpay()
    monkeypatch.setattr(routes, "_client", lambda: fake)
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_fake")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", "secret")

    with TestClient(app) as client:
        created = client.post("/api/journeys", json={"amount_inr": 359}).json()
        jid = created["journey"]["journey_id"]
        fake.payments = [{
            "id": "pay_JOURNEY_SUCCESS",
            "order_id": "order_JOURNEY1",
            "amount": 35900,
            "currency": "INR",
            "status": "captured",
            "method": "netbanking",
            "bank": "CNRB",
            "created_at": 1788101000,
        }]
        refreshed = client.post(f"/api/journeys/{jid}/refresh")
        assert refreshed.status_code == 200
        assert refreshed.json()["status"] == "PAID"

        analyzed = client.post(
            f"/api/journeys/{jid}/analyze",
            json={"auto_execute_test_action": True, "force_redecide": True},
        )
        assert analyzed.status_code == 200
        body = analyzed.json()
        assert body["status"] == "PAID"
        assert body["decision"] is None
        assert body["actions"] == []
