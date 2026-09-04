from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.guardrails import test_actions_enabled
from app.services.razorpay_client import RazorpayClient
from app.services.store import (
    append_audit,
    connect,
    find_action_by_provider_id,
    get_action,
    get_decision,
    get_event,
    list_actions_for_event,
    save_action,
    update_action,
    update_decision_links,
)


def record_simulated_action(audit_id: str, event_id: str, action_type: str, expected_recovery: float = 0.0) -> dict:
    action_id = f"act-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    action = {
        "action_id": action_id,
        "audit_id": audit_id,
        "event_id": event_id,
        "action_type": action_type,
        "execution_mode": "simulation",
        "status": "SIMULATED",
        "provider_payload": {},
        "expected_recovery": expected_recovery,
        "actual_recovery": 0.0,
        "created_at": now,
        "executed_at": now,
        "verified_at": now,
    }
    save_action(action)
    update_decision_links(audit_id, action_id=action_id)
    append_audit("action", action_id, "action.simulated", {"event_id": event_id, "action_type": action_type})
    return action


def _existing_real_payment_link(event_id: str) -> dict | None:
    """
    Return an already-created Razorpay Test Mode
    Payment Link for this original failed payment.
    """
    for action in list_actions_for_event(event_id):
        if (
            action.get("execution_mode") == "razorpay_test_mode"
            and action.get("action_type") == "payment_link"
        ):
            return action
    return None


def _acquire_provider_action_lock(
    event_id: str,
    action_id: str,
    audit_id: str,
) -> bool:
    """
    Atomically reserve one provider Payment Link
    per original failed payment.
    """
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_action_locks (
                event_id TEXT PRIMARY KEY,
                action_id TEXT NOT NULL,
                audit_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        cur = conn.execute(
            """
            INSERT OR IGNORE INTO provider_action_locks
                (event_id, action_id, audit_id, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                event_id,
                action_id,
                audit_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        conn.commit()
        return cur.rowcount == 1


def _release_provider_action_lock(
    event_id: str,
    action_id: str,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM provider_action_locks
            WHERE event_id=? AND action_id=?
            """,
            (event_id, action_id),
        )
        conn.commit()


def execute_payment_link_from_decision(audit_id: str, *, approved: bool = False) -> dict:
    decision = get_decision(audit_id)
    if not decision:
        raise ValueError("decision not found")
    event = get_event(decision["event_id"])
    if not event:
        raise ValueError("event not found")
    if decision["recommended_action"] != "payment_link":
        return record_simulated_action(audit_id, event.event_id, decision["recommended_action"])

    guardrail = decision.get("guardrail_status") or "SIMULATION_ONLY"
    if guardrail == "APPROVAL_REQUIRED" and not approved:
        raise PermissionError("human approval required")
    if guardrail == "BLOCKED":
        raise PermissionError("decision is blocked by guardrails")
    if guardrail not in {"AUTO_ALLOWED_TEST", "APPROVAL_REQUIRED"}:
        return record_simulated_action(audit_id, event.event_id, "payment_link", decision.get("revenue_at_risk", 0.0))
    if not test_actions_enabled():
        raise PermissionError("MERCHANTOS_TEST_ACTIONS_ENABLED is not enabled")

    # ---------------------------------------------------------
    # PROVIDER ACTION IDEMPOTENCY
    # Only one real Razorpay Payment Link may exist
    # for one original failed payment.
    # ---------------------------------------------------------

    existing_action = _existing_real_payment_link(
        event.event_id
    )

    if existing_action:
        update_decision_links(
            audit_id,
            action_id=existing_action["action_id"],
        )

        append_audit(
            "action",
            existing_action["action_id"],
            "action.idempotent_reuse",
            {
                "event_id": event.event_id,
                "requested_by_decision": audit_id,
            },
        )

        return existing_action

    client = RazorpayClient()

    if not client.configured:
        raise PermissionError(
            "Razorpay Test Mode is not safely configured"
        )

    action_id = f"act-{uuid.uuid4().hex[:12]}"

    reserved = _acquire_provider_action_lock(
        event.event_id,
        action_id,
        audit_id,
    )

    if not reserved:
        existing_action = _existing_real_payment_link(
            event.event_id
        )

        if existing_action:
            update_decision_links(
                audit_id,
                action_id=existing_action["action_id"],
            )
            return existing_action

        raise RuntimeError(
            "A recovery Payment Link for this payment "
            "is already being created. Refresh before retrying."
        )

    reference_id = f"mos-{action_id}"[:40]

    try:
        link = client.create_payment_link(
            amount_inr=event.amount,
            reference_id=reference_id,
            description=(
                f"MerchantOS Test Mode recovery for "
                f"{event.order_id}"
            ),
            notes={
                "merchantos_action_id": action_id,
                "merchantos_event_id": event.event_id,
                "merchantos_original_payment":
                    event.payment_id or "unknown",
                "merchantos_environment": "test_mode",
            },
        )

    except Exception:
        _release_provider_action_lock(
            event.event_id,
            action_id,
        )
        raise
    now = datetime.now(timezone.utc).isoformat()
    action = {
        "action_id": action_id,
        "audit_id": audit_id,
        "event_id": event.event_id,
        "action_type": "payment_link",
        "execution_mode": "razorpay_test_mode",
        "status": "EXECUTED_TEST",
        "provider_entity_type": "payment_link",
        "provider_entity_id": link.get("id"),
        "provider_payload": link,
        # Compare verified recovery against the Digital Twin expectation for
        # the chosen intervention, not against the broader revenue-at-risk
        # estimate. Older records remain readable; new v1.4.1 actions are
        # semantically aligned with the Digital Twin.
        "expected_recovery": float((decision.get("simulation") or {}).get("payment_link") or decision.get("revenue_at_risk") or 0.0),
        "actual_recovery": float(link.get("amount_paid") or 0) / 100.0,
        "created_at": now,
        "executed_at": now,
        "verified_at": None,
    }
    save_action(action)
    update_decision_links(audit_id, action_id=action_id)
    append_audit("action", action_id, "action.testmode_payment_link_created", {
        "event_id": event.event_id,
        "provider_entity_id": link.get("id"),
        "amount_inr": event.amount,
        "short_url": link.get("short_url"),
    })
    return action


def verify_action(action_id: str) -> dict:
    action = get_action(action_id)
    if not action:
        raise ValueError("action not found")
    if action.get("provider_entity_type") != "payment_link" or not action.get("provider_entity_id"):
        return action
    client = RazorpayClient()
    link = client.fetch_payment_link(action["provider_entity_id"])
    status = str(link.get("status") or "unknown").lower()
    actual = float(link.get("amount_paid") or 0) / 100.0
    if status == "paid":
        action_status = "VERIFIED_RECOVERED"
    elif status == "partially_paid":
        action_status = "VERIFIED_PARTIAL"
    elif status in {"cancelled", "expired"}:
        action_status = "VERIFIED_FAILED"
    else:
        action_status = "PENDING_VERIFICATION"
    updated = update_action(
        action_id,
        status=action_status,
        provider_payload=link,
        actual_recovery=actual,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )
    append_audit("action", action_id, "action.verified", {"provider_status": status, "actual_recovery_inr": actual})
    return updated or action


def update_action_from_payment_link_webhook(payment_link: dict, event_type: str) -> dict | None:
    link_id = str(payment_link.get("id") or "")
    if not link_id:
        return None
    action = find_action_by_provider_id(link_id)
    if not action:
        return None
    status = str(payment_link.get("status") or "unknown")
    actual = float(payment_link.get("amount_paid") or 0) / 100.0
    mapped = {
        "payment_link.paid": "VERIFIED_RECOVERED",
        "payment_link.partially_paid": "VERIFIED_PARTIAL",
        "payment_link.cancelled": "VERIFIED_FAILED",
        "payment_link.expired": "VERIFIED_FAILED",
    }.get(event_type, "PENDING_VERIFICATION")
    updated = update_action(
        action["action_id"], status=mapped, provider_payload=payment_link,
        actual_recovery=actual, verified_at=datetime.now(timezone.utc).isoformat(),
    )
    append_audit("action", action["action_id"], event_type, {"provider_status": status, "actual_recovery_inr": actual})
    return updated
