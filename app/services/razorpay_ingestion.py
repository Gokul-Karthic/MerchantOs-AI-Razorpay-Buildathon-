from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models.schemas import PaymentEvent
from app.services.privacy import stable_hash


def _dt_from_unix(value: Any) -> datetime:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc)


def _customer_id(payment: dict[str, Any], context: dict[str, Any]) -> str:
    if payment.get("customer_id"):
        return str(payment["customer_id"])
    if context.get("customer_ref") and context.get("customer_ref") != "unknown":
        return str(context["customer_ref"])
    if payment.get("email"):
        return stable_hash(str(payment["email"]), "customer")
    if payment.get("contact"):
        return stable_hash(str(payment["contact"]), "customer")
    return f"payment_customer_{payment.get('id', 'unknown')}"


def _instrument_id(payment: dict[str, Any]) -> str:
    if payment.get("card_id"):
        return str(payment["card_id"])
    if payment.get("token_id"):
        return str(payment["token_id"])
    upi = payment.get("upi") or {}
    vpa = payment.get("vpa") or upi.get("vpa")
    if vpa:
        return stable_hash(str(vpa), "upi")
    return "unknown"


def event_type_from_payment(payment: dict[str, Any], webhook_event: str | None = None) -> str:
    if webhook_event and webhook_event.startswith("payment."):
        return webhook_event
    status = str(payment.get("status") or "unknown").lower()
    if status in {"failed", "captured", "authorized"}:
        return f"payment.{status}"
    return f"payment.{status}"


def normalize_payment_entity(
    payment: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    source: str,
    webhook_event: str | None = None,
) -> PaymentEvent:
    context = context or {}
    payment_id = str(payment.get("id") or "")
    if not payment_id.startswith("pay_"):
        raise ValueError("Razorpay payment entity is missing a valid pay_ id")
    order_id = str(payment.get("order_id") or context.get("order_id") or "unknown")
    amount_subunits = payment.get("amount") or 0
    amount = float(amount_subunits) / 100.0
    if amount <= 0:
        raise ValueError("Razorpay payment amount must be positive")

    error_metadata = {
        key: payment.get(key)
        for key in ("error_code", "error_description", "error_source", "error_step", "error_reason")
        if payment.get(key) is not None
    }
    metadata = {
        "provider": "razorpay",
        "environment": "test",
        "provider_status": payment.get("status"),
        "description": payment.get("description"),
        "wallet": payment.get("wallet"),
        "vpa_present": bool(payment.get("vpa") or (payment.get("upi") or {}).get("vpa")),
        "card_id": payment.get("card_id"),
        "razorpay_created_at": payment.get("created_at"),
        **error_metadata,
    }

    return PaymentEvent(
        event_id=f"rzp-payment:{payment_id}",
        event_type=event_type_from_payment(payment, webhook_event),
        order_id=order_id,
        payment_id=payment_id,
        customer_id=_customer_id(payment, context),
        amount=amount,
        currency=str(payment.get("currency") or "INR"),
        method=str(payment.get("method") or "unknown"),
        bank=str(payment.get("bank") or "unknown"),
        device_id=str(context.get("device_id") or "unknown"),
        ip_address=str(context.get("ip_address") or "unknown"),
        instrument_id=_instrument_id(payment),
        merchant_id=str(context.get("merchant_id") or "merchant-test"),
        timestamp=_dt_from_unix(payment.get("created_at")),
        source=source,
        scenario_label=str(context.get("scenario_label") or "UNLABELED"),
        metadata=metadata,
    )


def payment_from_webhook(payload: dict[str, Any]) -> dict[str, Any] | None:
    return (((payload.get("payload") or {}).get("payment") or {}).get("entity"))


def payment_link_from_webhook(payload: dict[str, Any]) -> dict[str, Any] | None:
    return (((payload.get("payload") or {}).get("payment_link") or {}).get("entity"))
