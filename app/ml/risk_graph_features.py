from __future__ import annotations

from collections import defaultdict, deque
from datetime import timedelta

import pandas as pd

from app.models.schemas import PaymentEvent


FEATURE_COLUMNS = [
    "amount",
    "hour",
    "customer_events_before",
    "customer_fail_rate_before",
    "device_events_before",
    "device_unique_customers_before",
    "device_fail_rate_before",
    "device_velocity_60m",
    "ip_events_before",
    "ip_unique_customers_before",
    "ip_fail_rate_before",
    "ip_velocity_60m",
    "instrument_events_before",
    "instrument_unique_customers_before",
    "instrument_fail_rate_before",
    "instrument_velocity_60m",
    "merchant_events_before",
    "merchant_fail_rate_before",
    "device_ip_pair_events_before",
    "shared_entity_signal",
    "shared_entity_types_before",
    "device_customer_diversity_before",
    "ip_customer_diversity_before",
    "instrument_customer_diversity_before",
]


def _rate(failures: int, events: int) -> float:
    return failures / events if events else 0.0


def temporal_graph_features(events: list[PaymentEvent]) -> pd.DataFrame:
    """Generate event-time graph features using only information available at that timestamp.

    The state is updated *after* each row is featurized, preventing future leakage.
    """
    ordered = sorted(events, key=lambda e: (e.timestamp, e.event_id))
    counts = defaultdict(int)
    failures = defaultdict(int)
    customers_by_entity: dict[tuple[str, str], set[str]] = defaultdict(set)
    velocity: dict[tuple[str, str], deque] = defaultdict(deque)
    pair_counts = defaultdict(int)
    rows: list[dict] = []

    for e in ordered:
        # Placeholder entity values must not become shared graph hubs. Treat
        # unknown/default resources as event-local identities.
        device_value = e.device_id if e.device_id not in {"", "unknown"} else f"unknown-device:{e.event_id}"
        ip_value = e.ip_address if e.ip_address not in {"", "0.0.0.0", "unknown"} else f"unknown-ip:{e.event_id}"
        instrument_value = e.instrument_id if e.instrument_id not in {"", "unknown"} else f"unknown-instrument:{e.event_id}"
        keys = {
            "customer": ("customer", e.customer_id),
            "device": ("device", device_value),
            "ip": ("ip", ip_value),
            "instrument": ("instrument", instrument_value),
            "merchant": ("merchant", e.merchant_id),
        }
        cutoff = e.timestamp - timedelta(minutes=60)
        velocities: dict[str, int] = {}
        for name in ("device", "ip", "instrument"):
            q = velocity[keys[name]]
            while q and q[0] < cutoff:
                q.popleft()
            velocities[name] = len(q)

        d_customers = len(customers_by_entity[keys["device"]])
        ip_customers = len(customers_by_entity[keys["ip"]])
        inst_customers = len(customers_by_entity[keys["instrument"]])
        shared_signal = max(d_customers, ip_customers, inst_customers)
        shared_entity_types = sum(value >= 2 for value in (d_customers, ip_customers, inst_customers))
        device_customer_diversity = d_customers / counts[keys["device"]] if counts[keys["device"]] else 0.0
        ip_customer_diversity = ip_customers / counts[keys["ip"]] if counts[keys["ip"]] else 0.0
        instrument_customer_diversity = inst_customers / counts[keys["instrument"]] if counts[keys["instrument"]] else 0.0

        # Future ML training may use only controlled labels attached to genuine
        # Razorpay Test Mode transactions. UNLABELED rows are marked -1 and must
        # be excluded from supervised training.
        label = 1 if e.scenario_label == "CONTROLLED_ABUSE" else (0 if e.scenario_label in {"NORMAL", "LEGIT_SHARED_NETWORK"} else -1)
        rows.append({
            "event_id": e.event_id,
            "timestamp": e.timestamp,
            "label": label,
            "scenario_label": e.scenario_label,
            "amount": e.amount,
            "hour": e.timestamp.hour + e.timestamp.minute / 60.0,
            "customer_events_before": counts[keys["customer"]],
            "customer_fail_rate_before": _rate(failures[keys["customer"]], counts[keys["customer"]]),
            "device_events_before": counts[keys["device"]],
            "device_unique_customers_before": d_customers,
            "device_fail_rate_before": _rate(failures[keys["device"]], counts[keys["device"]]),
            "device_velocity_60m": velocities["device"],
            "ip_events_before": counts[keys["ip"]],
            "ip_unique_customers_before": ip_customers,
            "ip_fail_rate_before": _rate(failures[keys["ip"]], counts[keys["ip"]]),
            "ip_velocity_60m": velocities["ip"],
            "instrument_events_before": counts[keys["instrument"]],
            "instrument_unique_customers_before": inst_customers,
            "instrument_fail_rate_before": _rate(failures[keys["instrument"]], counts[keys["instrument"]]),
            "instrument_velocity_60m": velocities["instrument"],
            "merchant_events_before": counts[keys["merchant"]],
            "merchant_fail_rate_before": _rate(failures[keys["merchant"]], counts[keys["merchant"]]),
            "device_ip_pair_events_before": pair_counts[(e.device_id, e.ip_address)],
            "shared_entity_signal": shared_signal,
            "shared_entity_types_before": shared_entity_types,
            "device_customer_diversity_before": device_customer_diversity,
            "ip_customer_diversity_before": ip_customer_diversity,
            "instrument_customer_diversity_before": instrument_customer_diversity,
        })

        is_failure = int(e.event_type == "payment.failed")
        for key in keys.values():
            counts[key] += 1
            failures[key] += is_failure
            customers_by_entity[key].add(e.customer_id)
        for name in ("device", "ip", "instrument"):
            velocity[keys[name]].append(e.timestamp)
        pair_counts[(e.device_id, e.ip_address)] += 1

    return pd.DataFrame(rows)
