from __future__ import annotations

from app.models.schemas import InterventionOption, PayGuardIncident, PaymentEvent


def _success_rate(events: list[PaymentEvent], *, method: str | None = None, bank: str | None = None) -> tuple[float, int]:
    rows = [e for e in events if (method is None or e.method == method) and (bank is None or e.bank == bank)]
    terminal = [e for e in rows if e.event_type in {"payment.captured", "payment.failed"}]
    if not terminal:
        return 0.50, 0
    success = sum(e.event_type == "payment.captured" for e in terminal)
    return success / len(terminal), len(terminal)


def simulate_interventions(
    event: PaymentEvent,
    events: list[PaymentEvent],
    *,
    risk_score: float,
    revenue_at_risk: float,
    incident: PayGuardIncident | None = None,
) -> list[InterventionOption]:
    same_rate, same_n = _success_rate(events, method=event.method, bank=event.bank)
    global_rate, global_n = _success_rate(events)
    prior_same_order_failures = sum(
        e.order_id == event.order_id and e.event_type == "payment.failed" and e.timestamp <= event.timestamp
        for e in events
    )

    retry_p = same_rate if same_n >= 3 else 0.42
    retry_p *= max(0.35, 1.0 - 0.18 * max(0, prior_same_order_failures - 1))
    if incident and incident.recent_failure_rate >= 0.70:
        retry_p *= 0.45

    alt_p = max(global_rate if global_n >= 5 else 0.56, 0.50)
    if incident:
        alt_p = min(0.82, alt_p + 0.10)

    link_p = 0.62
    if incident and incident.recent_failure_rate >= 0.60:
        link_p = 0.70
    if prior_same_order_failures >= 2:
        link_p = min(0.80, link_p + 0.08)

    wait_p = 0.28 if incident else 0.22

    definitions = [
        ("retry_same_method", retry_p, 2.0, 0.28, "Retry preserves the original method; repeated failures and active degradation reduce its expected value."),
        ("alternate_method", alt_p, 4.0, 0.18, "Offer a different payment route when the current method/bank is degraded."),
        ("payment_link", link_p, 6.0, 0.15, "Create a Razorpay Test Mode Payment Link so the customer can choose another available method."),
        ("wait", wait_p, 1.0, 0.05, "Wait avoids extra friction but risks losing the recovery opportunity."),
        ("escalate_review", 0.0, 25.0, 0.0, "Human review is preferred when abuse risk or financial impact is too high."),
    ]

    options: list[InterventionOption] = []
    for action, probability, cost, exposure_factor, rationale in definitions:
        probability = max(0.0, min(0.95, probability))
        if action != "escalate_review":
            probability *= max(0.15, 1.0 - 0.55 * risk_score)
        expected = revenue_at_risk * probability
        risk_penalty = event.amount * risk_score * exposure_factor
        net = expected - cost - risk_penalty
        if action == "escalate_review":
            operational_risk = "low"
        elif risk_score >= 0.70 or exposure_factor >= 0.25:
            operational_risk = "high"
        elif risk_score >= 0.35:
            operational_risk = "medium"
        else:
            operational_risk = "low"
        options.append(InterventionOption(
            action=action,
            expected_recovery_probability=round(probability, 4),
            expected_recovery_inr=round(expected, 2),
            expected_cost_inr=round(cost, 2),
            risk_penalty_inr=round(risk_penalty, 2),
            expected_net_value_inr=round(net, 2),
            operational_risk=operational_risk,
            rationale=rationale,
        ))
    return sorted(options, key=lambda x: x.expected_net_value_inr, reverse=True)
