from __future__ import annotations

from app.agents.decision_agent import make_decision
from app.ml.payguard import detect_incidents
from app.services.actions import execute_payment_link_from_decision
from app.services.store import (
    append_audit,
    latest_decision_for_event,
    list_actions_for_event,
    list_events,
    save_incidents,
)


def _needs_recovery(event, events) -> bool:
    if event.event_type != "payment.failed":
        return False
    return not any(
        e.order_id == event.order_id
        and e.event_type == "payment.captured"
        and e.timestamp >= event.timestamp
        for e in events
    )


def _real_provider_action_for_event(event_id: str) -> dict | None:
    """
    Return an existing real Razorpay Test Mode Payment Link
    for this failed payment, if one already exists.
    """
    for action in list_actions_for_event(event_id):
        if (
            action.get("execution_mode") == "razorpay_test_mode"
            and action.get("provider_entity_type") == "payment_link"
        ):
            return action
    return None


def run_cycle(
    *,
    limit: int = 25,
    auto_execute_test_actions: bool = False,
    force_redecide: bool = False,
) -> dict:

    events = list_events()

    incidents = detect_incidents(events)
    save_incidents(incidents)

    failed = [
        e for e in events
        if _needs_recovery(e, events)
    ][:limit]

    decisions = []
    skipped = []

    existing_considered = 0

    actions_started = []
    actions_already_present = []

    approval_required = []
    simulation_only = []
    blocked = []

    execution_errors = []

    for event in failed:

        existing = latest_decision_for_event(
            event.event_id
        )

        # ----------------------------------------------------
        # EXISTING DECISION
        # ----------------------------------------------------

        if existing and not force_redecide:

            skipped.append(event.event_id)

            # Safe simulation does not create another decision.
            if not auto_execute_test_actions:
                continue

            # Bounded cycle should continue an existing decision.
            existing_considered += 1

            guardrail = str(
                existing.get("guardrail_status")
                or "SIMULATION_ONLY"
            )

            action = str(
                existing.get("recommended_action")
                or ""
            )

            # Human approval is still required.
            if guardrail == "APPROVAL_REQUIRED":
                approval_required.append(
                    event.event_id
                )
                continue

            # Blocked payments remain blocked.
            if guardrail == "BLOCKED":
                blocked.append(
                    event.event_id
                )
                continue

            # Only Payment Link is a real provider action.
            if (
                guardrail != "AUTO_ALLOWED_TEST"
                or action != "payment_link"
            ):
                simulation_only.append(
                    event.event_id
                )
                continue

            # Do not make another Payment Link when one
            # already exists for this failed payment.
            current_action = (
                _real_provider_action_for_event(
                    event.event_id
                )
            )

            if current_action:
                actions_already_present.append(
                    current_action["action_id"]
                )
                continue

            try:
                executed = (
                    execute_payment_link_from_decision(
                        existing["audit_id"]
                    )
                )

                if (
                    executed.get("execution_mode")
                    == "razorpay_test_mode"
                ):
                    actions_started.append(
                        executed["action_id"]
                    )

            except Exception as exc:
                execution_errors.append(
                    {
                        "event_id":
                            event.event_id,
                        "error":
                            str(exc),
                    }
                )

            continue

        # ----------------------------------------------------
        # NEW DECISION
        # ----------------------------------------------------

        decision = make_decision(
            event,
            auto_execute_test_action=
                auto_execute_test_actions,
        )

        dumped = decision.model_dump(
            mode="json"
        )

        decisions.append(dumped)

        if auto_execute_test_actions:

            if dumped.get("action_id"):
                actions_started.append(
                    dumped["action_id"]
                )

            elif (
                dumped.get("guardrail_status")
                == "APPROVAL_REQUIRED"
            ):
                approval_required.append(
                    event.event_id
                )

            elif (
                dumped.get("guardrail_status")
                == "BLOCKED"
            ):
                blocked.append(
                    event.event_id
                )

            else:
                simulation_only.append(
                    event.event_id
                )

    summary = {
        "observed_events":
            len(events),

        "open_failed_candidates":
            len(failed),

        "payguard_incidents":
            len(incidents),

        "new_decisions":
            len(decisions),

        "skipped_existing_decisions":
            len(skipped),

        "existing_decisions_considered_for_execution":
            existing_considered,

        "provider_actions_started":
            len(actions_started),

        "provider_action_ids":
            actions_started,

        "provider_actions_already_present":
            len(actions_already_present),

        "approval_required":
            len(approval_required),

        "simulation_only":
            len(simulation_only),

        "blocked":
            len(blocked),

        "execution_errors":
            execution_errors,

        "auto_execute_requested":
            auto_execute_test_actions,

        "decisions":
            decisions,
    }

    append_audit(
        "orchestrator",
        "merchantos",
        "orchestrator.cycle",
        {
            k: v
            for k, v in summary.items()
            if k != "decisions"
        },
    )

    return summary
