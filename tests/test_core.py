from datetime import datetime, timedelta, timezone

from app.ml.revenue import intervention_simulation
from app.ml.risk_graph import cluster_summary, score_event
from app.models.schemas import PaymentEvent


def make_event(event_id="pay_1", failed=True, device="d1", ip="ip1", customer="c1", instrument="i1", minute=0):
    return PaymentEvent(
        event_id=f"rzp-payment:{event_id}",
        event_type="payment.failed" if failed else "payment.captured",
        order_id=f"order-{event_id}",
        payment_id=event_id,
        customer_id=customer,
        amount=5000,
        method="upi",
        bank="HDFC",
        device_id=device,
        ip_address=ip,
        instrument_id=instrument,
        source="razorpay_test_mode_api_sync",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=minute),
    )


def test_graph_score_increases_for_shared_testmode_entities():
    target = make_event()
    events = [target] + [make_event(f"pay_{i}", device="d1", ip="ip1", instrument="i1", customer=f"c{i}", minute=i) for i in range(2, 8)]
    assert score_event(target, events) > score_event(target, [target])


def test_unknown_entities_do_not_create_shared_risk():
    target = make_event(device="unknown", ip="unknown", instrument="unknown")
    others = [make_event(f"pay_{i}", device="unknown", ip="unknown", instrument="unknown", customer=f"c{i}", minute=i) for i in range(2, 15)]
    assert score_event(target, [target] + others) == 0.05


def test_intervention_values_are_bounded():
    sim = intervention_simulation(make_event(), 4000)
    assert sim["retry"] > sim["alternate_method"] > sim["wait"]
    assert all(v >= 0 for v in sim.values())


def test_dense_testmode_graph_can_be_review_only_high_risk():
    events = [
        make_event(
            f"pay_{i}",
            device="shared-device",
            ip="shared-ip",
            instrument="shared-instrument",
            customer=f"customer-{i}",
            minute=i,
        )
        for i in range(8)
    ]
    clusters = cluster_summary(events)
    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.classification == "HIGH_RISK_RING"
    assert cluster.action_allowed is False
    assert cluster.detector == "razorpay-testmode-graph-evidence"
