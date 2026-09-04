from __future__ import annotations

from app.models.schemas import PaymentEvent


def revenue_at_risk(event: PaymentEvent, events: list[PaymentEvent]) -> float:
    """Estimate recoverable revenue using only observed Razorpay Test Mode history."""
    if event.event_type != "payment.failed":
        return 0.0
    related = [e for e in events if e.method == event.method and e.bank == event.bank and e.event_type in {"payment.captured", "payment.failed"}]
    successes = sum(e.event_type == "payment.captured" for e in related)
    failures = sum(e.event_type == "payment.failed" for e in related)
    if successes + failures < 3:
        recoverability = 0.65
    else:
        observed_success = successes / (successes + failures)
        # Avoid treating a tiny Test Mode sample as a precise probability.
        recoverability = max(0.30, min(0.85, 0.35 + 0.50 * observed_success))
    return round(event.amount * recoverability, 2)


def intervention_simulation(event: PaymentEvent, revenue_risk: float) -> dict[str, float]:
    # Backward-compatible summary; the full Digital Twin is in app.ml.digital_twin.
    return {
        "retry": round(revenue_risk * 0.82, 2),
        "alternate_method": round(revenue_risk * 0.67, 2),
        "payment_link": round(revenue_risk * 0.62, 2),
        "wait": round(revenue_risk * 0.34, 2),
        "escalate": 0.0,
    }
