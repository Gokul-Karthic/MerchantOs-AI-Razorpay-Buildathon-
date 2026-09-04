from __future__ import annotations

import os
from dataclasses import dataclass

from app.models.schemas import PaymentEvent
from app.services.razorpay_client import RazorpayClient


MAX_AUTO_TEST_ACTION_INR = float(os.getenv("MERCHANTOS_MAX_AUTO_TEST_ACTION_INR", "1000"))
MAX_APPROVAL_TEST_ACTION_INR = float(os.getenv("MERCHANTOS_MAX_APPROVAL_TEST_ACTION_INR", "10000"))


@dataclass(frozen=True)
class GuardrailDecision:
    status: str
    reason: str
    provider_action_allowed: bool


def test_actions_enabled() -> bool:
    return os.getenv("MERCHANTOS_TEST_ACTIONS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def evaluate_guardrails(event: PaymentEvent, *, risk_score: float, action: str, review_threshold: float = 0.64) -> GuardrailDecision:
    if not event.source.startswith("razorpay_test_mode"):
        return GuardrailDecision("BLOCKED", "Only Razorpay Test Mode events are accepted.", False)
    if event.event_type != "payment.failed" and action not in {"monitor", "escalate_review"}:
        return GuardrailDecision("BLOCKED", "Recovery actions require a failed Test Mode payment.", False)
    # Experiment labels are ground truth for offline training/evaluation only.
    # Operational guardrails must never use the current event label.
    if risk_score >= review_threshold:
        return GuardrailDecision(
            "BLOCKED",
            f"RiskNet review threshold reached ({risk_score:.2f} >= {review_threshold:.2f}); provider recovery action is blocked and routed to review.",
            False,
        )
    if action in {"monitor", "wait", "retry_same_method", "alternate_method", "escalate_review"}:
        return GuardrailDecision("SIMULATION_ONLY", "This intervention is recommendation/simulation only in MerchantOS.", False)
    if action != "payment_link":
        return GuardrailDecision("BLOCKED", "Unsupported provider action.", False)

    client = RazorpayClient()
    if not client.configured:
        return GuardrailDecision("BLOCKED", "Razorpay Test Mode credentials are not safely configured.", False)
    if event.amount > MAX_APPROVAL_TEST_ACTION_INR:
        return GuardrailDecision("BLOCKED", f"Amount exceeds ₹{MAX_APPROVAL_TEST_ACTION_INR:,.0f} Test Mode action ceiling.", False)
    if risk_score >= 0.55 or event.amount > MAX_AUTO_TEST_ACTION_INR:
        return GuardrailDecision("APPROVAL_REQUIRED", "Test Mode Payment Link requires human approval because of amount/risk.", True)
    if not test_actions_enabled():
        return GuardrailDecision("SIMULATION_ONLY", "Set MERCHANTOS_TEST_ACTIONS_ENABLED=true to allow bounded Razorpay Test Mode Payment Link creation.", False)
    return GuardrailDecision("AUTO_ALLOWED_TEST", "Low-risk bounded action is allowed in Razorpay Test Mode only.", True)
