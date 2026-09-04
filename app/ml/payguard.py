from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from datetime import timedelta

from app.models.schemas import PayGuardIncident, PaymentEvent


RECENT_WINDOW_MINUTES = 60
BASELINE_WINDOW_HOURS = 24
MIN_RECENT_TRANSACTIONS = 3


def _is_success(event: PaymentEvent) -> bool:
    return event.event_type in {"payment.captured", "order.paid"}


def _is_failure(event: PaymentEvent) -> bool:
    return event.event_type == "payment.failed"


def _root_cause(events: list[PaymentEvent]) -> tuple[str, list[str]]:
    failures = [e for e in events if _is_failure(e)]
    if not failures:
        return "No dominant failure cause detected.", []
    fields = {
        "error_reason": Counter(str(e.metadata.get("error_reason") or "unknown") for e in failures),
        "error_source": Counter(str(e.metadata.get("error_source") or "unknown") for e in failures),
        "error_step": Counter(str(e.metadata.get("error_step") or "unknown") for e in failures),
    }
    evidence: list[str] = []
    parts: list[str] = []
    for key, counter in fields.items():
        value, count = counter.most_common(1)[0]
        if value != "unknown":
            share = count / len(failures)
            evidence.append(f"{count}/{len(failures)} failures share {key}={value} ({share:.0%})")
            if share >= 0.5:
                parts.append(f"{key.replace('_', ' ')} {value}")
    if not parts:
        return "Mixed payment failures; no single provider cause dominates.", evidence
    return "Dominant failure pattern: " + ", ".join(parts) + ".", evidence


def detect_incidents(events: list[PaymentEvent]) -> list[PayGuardIncident]:
    if not events:
        return []
    ordered = sorted(events, key=lambda e: (e.timestamp, e.event_id))
    anchor = ordered[-1].timestamp
    recent_start = anchor - timedelta(minutes=RECENT_WINDOW_MINUTES)
    baseline_start = recent_start - timedelta(hours=BASELINE_WINDOW_HOURS)

    grouped: dict[tuple[str, str], list[PaymentEvent]] = defaultdict(list)
    for event in ordered:
        grouped[(event.method or "unknown", event.bank or "unknown")].append(event)

    incidents: list[PayGuardIncident] = []
    for (method, bank), group in grouped.items():
        recent = [e for e in group if recent_start <= e.timestamp <= anchor]
        if len(recent) < MIN_RECENT_TRANSACTIONS:
            continue
        recent_failures = [e for e in recent if _is_failure(e)]
        recent_rate = len(recent_failures) / len(recent)
        baseline = [e for e in group if baseline_start <= e.timestamp < recent_start]
        baseline_terminal = [e for e in baseline if _is_failure(e) or _is_success(e)]
        if baseline_terminal:
            baseline_rate = sum(_is_failure(e) for e in baseline_terminal) / len(baseline_terminal)
        else:
            # Conservative prior when a Test Mode experiment has no historical baseline yet.
            baseline_rate = 0.15
        degradation = max(0.0, recent_rate - baseline_rate)
        if len(recent_failures) < 2 or recent_rate < 0.50 or degradation < 0.20:
            continue

        failed_amount = sum(e.amount for e in recent_failures)
        # The estimate is transparent: 65% of failed value is considered at risk/recoverable.
        rar = round(failed_amount * 0.65, 2)
        if recent_rate >= 0.90 and len(recent) >= 5:
            severity = "critical"
        elif recent_rate >= 0.75 or rar >= 25_000:
            severity = "high"
        elif recent_rate >= 0.60 or rar >= 5_000:
            severity = "medium"
        else:
            severity = "low"

        cause, evidence = _root_cause(recent)
        evidence = [
            f"{len(recent_failures)}/{len(recent)} recent {method}/{bank} payments failed ({recent_rate:.0%})",
            f"baseline failure rate {baseline_rate:.0%}; degradation +{degradation:.0%}",
            f"₹{failed_amount:,.2f} failed value in the recent window",
            *evidence,
        ]
        signature = f"{method}|{bank}"
        incident_id = "inc-" + hashlib.sha256(signature.encode()).hexdigest()[:12]
        incidents.append(PayGuardIncident(
            incident_id=incident_id,
            severity=severity,
            scope=f"{method}:{bank}",
            method=method,
            bank=bank,
            recent_transactions=len(recent),
            recent_failures=len(recent_failures),
            recent_failure_rate=round(recent_rate, 4),
            baseline_failure_rate=round(baseline_rate, 4),
            degradation=round(degradation, 4),
            revenue_at_risk=rar,
            root_cause=cause,
            evidence=evidence,
            window_start=recent_start,
            window_end=anchor,
        ))
    return sorted(incidents, key=lambda i: (i.severity in {"critical", "high"}, i.revenue_at_risk), reverse=True)


def incident_for_event(event: PaymentEvent, incidents: list[PayGuardIncident]) -> PayGuardIncident | None:
    for incident in incidents:
        if incident.method == event.method and incident.bank == event.bank:
            return incident
    return None
