from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta
from math import log1p
from typing import Any

import pandas as pd

from app.models.schemas import PaymentEvent


NUMERIC_FEATURES = [
    "amount_log",
    "is_failure",
    "is_captured",
    "customer_events_before",
    "customer_fail_rate_before",
    "customer_velocity_10m",
    "customer_velocity_60m",
    "customer_unique_methods_before",
    "customer_unique_orders_before",
    "order_attempts_before",
    "method_events_before",
    "method_fail_rate_before",
    "method_velocity_60m",
    "bank_events_before",
    "bank_fail_rate_before",
    "bank_velocity_60m",
    "instrument_known",
    "instrument_events_before",
    "instrument_unique_customers_before",
    "instrument_fail_rate_before",
    "instrument_velocity_60m",
    "customer_prior_label_count",
    "customer_prior_abuse_rate",
    "instrument_prior_label_count",
    "instrument_prior_abuse_rate",
]

CATEGORICAL_FEATURES = ["method", "bank"]


def _rate(a: int, b: int) -> float:
    return float(a / b) if b else 0.0


def identity_quality(events: list[PaymentEvent]) -> dict[str, Any]:
    labeled = [e for e in events if e.scenario_label != "UNLABELED"]
    customers = {e.customer_id for e in labeled}
    devices = {e.device_id for e in labeled if e.device_id not in {"", "unknown"}}
    ips = {e.ip_address for e in labeled if e.ip_address not in {"", "unknown", "0.0.0.0"}}
    known_instruments = [e.instrument_id for e in labeled if e.instrument_id not in {"", "unknown"}]
    customer_n = max(1, len(customers))
    device_reliable = len(devices) >= 3 and len(devices) / customer_n >= 0.10
    ip_reliable = len(ips) >= 3 and len(ips) / customer_n >= 0.10
    return {
        "labeled_events": len(labeled),
        "unique_customers": len(customers),
        "unique_devices": len(devices),
        "unique_ips": len(ips),
        "known_instrument_events": len(known_instruments),
        "unique_known_instruments": len(set(known_instruments)),
        "device_identity_reliable": device_reliable,
        "ip_identity_reliable": ip_reliable,
        "device_features_allowed": device_reliable,
        "ip_features_allowed": ip_reliable,
        "reason": (
            "Device/IP graph evidence is used only when identity diversity is credible. "
            "Collapsed localhost/browser identities are automatically suppressed from learned scoring."
        ),
    }


def temporal_behavior_features(events: list[PaymentEvent]) -> pd.DataFrame:
    """Leakage-safe behavioral features using only state known before each event.

    Scenario labels are used only to maintain *prior adjudication reputation* after an
    event has occurred. The current event's label is never used in its own features.
    """
    ordered = sorted(events, key=lambda e: (e.timestamp, e.event_id))
    counts = defaultdict(int)
    failures = defaultdict(int)
    customers_by_instrument: dict[str, set[str]] = defaultdict(set)
    methods_by_customer: dict[str, set[str]] = defaultdict(set)
    orders_by_customer: dict[str, set[str]] = defaultdict(set)
    q10: dict[tuple[str, str], deque] = defaultdict(deque)
    q60: dict[tuple[str, str], deque] = defaultdict(deque)
    prior_labels = defaultdict(lambda: [0, 0])  # [abuse, total]
    rows: list[dict[str, Any]] = []

    for e in ordered:
        customer = ("customer", e.customer_id)
        method = ("method", e.method or "unknown")
        bank = ("bank", e.bank or "unknown")
        order = ("order", e.order_id)
        instrument_known = e.instrument_id not in {"", "unknown"}
        instrument_key = ("instrument", e.instrument_id) if instrument_known else ("instrument", f"unknown:{e.event_id}")

        cutoff10 = e.timestamp - timedelta(minutes=10)
        cutoff60 = e.timestamp - timedelta(minutes=60)
        for key in (customer, method, bank, instrument_key):
            while q10[key] and q10[key][0] < cutoff10:
                q10[key].popleft()
            while q60[key] and q60[key][0] < cutoff60:
                q60[key].popleft()

        c_abuse, c_total = prior_labels[("customer", e.customer_id)]
        i_abuse, i_total = prior_labels[("instrument", e.instrument_id)] if instrument_known else (0, 0)
        # Beta(1,3) prior = 25% baseline, matching the controlled dataset prevalence target.
        c_rep = (c_abuse + 1.0) / (c_total + 4.0)
        i_rep = (i_abuse + 1.0) / (i_total + 4.0)

        label = 1 if e.scenario_label == "CONTROLLED_ABUSE" else (0 if e.scenario_label in {"NORMAL", "LEGIT_SHARED_NETWORK"} else -1)
        rows.append({
            "event_id": e.event_id,
            "timestamp": e.timestamp,
            "label": label,
            "scenario_label": e.scenario_label,
            "amount": float(e.amount),
            "amount_log": log1p(float(e.amount)),
            "method": e.method or "unknown",
            "bank": e.bank or "unknown",
            "is_failure": int(e.event_type == "payment.failed"),
            "is_captured": int(e.event_type == "payment.captured"),
            "customer_events_before": counts[customer],
            "customer_fail_rate_before": _rate(failures[customer], counts[customer]),
            "customer_velocity_10m": len(q10[customer]),
            "customer_velocity_60m": len(q60[customer]),
            "customer_unique_methods_before": len(methods_by_customer[e.customer_id]),
            "customer_unique_orders_before": len(orders_by_customer[e.customer_id]),
            "order_attempts_before": counts[order],
            "method_events_before": counts[method],
            "method_fail_rate_before": _rate(failures[method], counts[method]),
            "method_velocity_60m": len(q60[method]),
            "bank_events_before": counts[bank],
            "bank_fail_rate_before": _rate(failures[bank], counts[bank]),
            "bank_velocity_60m": len(q60[bank]),
            "instrument_known": int(instrument_known),
            "instrument_events_before": counts[instrument_key] if instrument_known else 0,
            "instrument_unique_customers_before": len(customers_by_instrument[e.instrument_id]) if instrument_known else 0,
            "instrument_fail_rate_before": _rate(failures[instrument_key], counts[instrument_key]) if instrument_known else 0.0,
            "instrument_velocity_60m": len(q60[instrument_key]) if instrument_known else 0,
            "customer_prior_label_count": c_total,
            "customer_prior_abuse_rate": c_rep,
            "instrument_prior_label_count": i_total,
            "instrument_prior_abuse_rate": i_rep,
        })

        is_failure = int(e.event_type == "payment.failed")
        for key in (customer, method, bank, order, instrument_key):
            counts[key] += 1
            failures[key] += is_failure
        for key in (customer, method, bank, instrument_key):
            q10[key].append(e.timestamp)
            q60[key].append(e.timestamp)
        methods_by_customer[e.customer_id].add(e.method or "unknown")
        orders_by_customer[e.customer_id].add(e.order_id)
        if instrument_known:
            customers_by_instrument[e.instrument_id].add(e.customer_id)

        # Only after feature generation can the controlled outcome update reputation.
        if label >= 0:
            prior_labels[("customer", e.customer_id)][0] += label
            prior_labels[("customer", e.customer_id)][1] += 1
            if instrument_known:
                prior_labels[("instrument", e.instrument_id)][0] += label
                prior_labels[("instrument", e.instrument_id)][1] += 1

    return pd.DataFrame(rows)
