from __future__ import annotations

from collections import defaultdict
from statistics import mean

import networkx as nx

from app.models.schemas import PaymentEvent, RiskCluster


# A cluster should require materially stronger event-level evidence than the
# operational event threshold. The trained event threshold is intentionally low
# because false negatives are expensive; using that same cutoff at cluster level
# would over-promote diffuse benign components.
CLUSTER_STRONG_EVENT_FLOOR = 0.35


def build_graph(events: list[PaymentEvent]) -> nx.Graph:
    """Build the full MerchantOS entity graph.

    Entity types intentionally mirror Stage 3: customer, device, IP, payment
    instrument, order and merchant. Transaction nodes preserve event evidence.
    """
    g = nx.Graph()
    for e in events:
        tx = f"tx:{e.event_id}"
        g.add_node(
            tx,
            kind="transaction",
            amount=e.amount,
            event_type=e.event_type,
            timestamp=e.timestamp.isoformat(),
        )
        for kind, value in (
            ("customer", e.customer_id),
            ("device", e.device_id),
            ("ip", e.ip_address),
            ("instrument", e.instrument_id),
            ("order", e.order_id),
            ("merchant", e.merchant_id),
        ):
            node = f"{kind}:{value}"
            g.add_node(node, kind=kind, value=value)
            g.add_edge(tx, node, relation=f"uses_{kind}")
    return g


def _valid_shared_entity(kind: str, value: str) -> bool:
    if kind == "device":
        return bool(value) and not value.startswith("unknown")
    if kind == "ip":
        return bool(value) and value != "0.0.0.0" and not value.startswith("unknown")
    if kind == "instrument":
        return bool(value) and not value.startswith("unknown")
    return True


def build_association_graph(events: list[PaymentEvent]) -> nx.Graph:
    """Graph used for ring discovery without merchant/order hub leakage.

    Merchant and order are present in the full evidence graph, but merchants are
    intentionally excluded from connectivity because a merchant is a legitimate
    high-degree hub that would collapse unrelated customers into one component.
    """
    g = nx.Graph()
    for e in events:
        tx = f"tx:{e.event_id}"
        g.add_node(tx, kind="transaction")
        for kind, value in (
            ("customer", e.customer_id),
            ("device", e.device_id),
            ("ip", e.ip_address),
            ("instrument", e.instrument_id),
        ):
            if not _valid_shared_entity(kind, value):
                continue
            node = f"{kind}:{value}"
            g.add_node(node, kind=kind, value=value)
            g.add_edge(tx, node)
    return g


def score_event(event: PaymentEvent, events: list[PaymentEvent]) -> float:
    """Deterministic graph-evidence score for Test Mode operations.

    This is deliberately not presented as a fraud probability. Missing graph
    entities are ignored so API-synced payments without browser context do not
    collapse into one artificial "unknown" cluster.
    """
    valid_device = _valid_shared_entity("device", event.device_id)
    valid_ip = _valid_shared_entity("ip", event.ip_address)
    valid_instrument = _valid_shared_entity("instrument", event.instrument_id)

    same_device = [e for e in events if valid_device and e.device_id == event.device_id]
    same_ip = [e for e in events if valid_ip and e.ip_address == event.ip_address]
    same_instrument = [e for e in events if valid_instrument and e.instrument_id == event.instrument_id]

    unique_customers_device = len({e.customer_id for e in same_device})
    unique_customers_ip = len({e.customer_id for e in same_ip})
    unique_customers_instrument = len({e.customer_id for e in same_instrument})
    linked = {e.event_id: e for e in (same_device + same_ip + same_instrument)}.values()
    repeated_failures = sum(e.event_type == "payment.failed" for e in linked)

    score = 0.05
    score += min(0.30, 0.07 * max(0, unique_customers_device - 1))
    score += min(0.24, 0.06 * max(0, unique_customers_ip - 1))
    score += min(0.30, 0.08 * max(0, unique_customers_instrument - 1))
    score += min(0.20, 0.02 * repeated_failures)
    return round(min(score, 0.99), 4)


def _component_evidence(
    tx_events: list[PaymentEvent],
) -> tuple[dict[str, list[str]], list[str], dict[tuple[str, str], set[str]]]:
    entity_values: dict[str, set[str]] = defaultdict(set)
    customers_by_entity: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in tx_events:
        for kind, value in (
            ("customer", e.customer_id),
            ("device", e.device_id),
            ("ip", e.ip_address),
            ("instrument", e.instrument_id),
            ("order", e.order_id),
            ("merchant", e.merchant_id),
        ):
            entity_values[kind].add(value)
            if kind in {"device", "ip", "instrument"} and _valid_shared_entity(kind, value):
                customers_by_entity[(kind, value)].add(e.customer_id)

    evidence: list[str] = []
    shared = sorted(
        (
            (len(customers), kind, value)
            for (kind, value), customers in customers_by_entity.items()
            if len(customers) >= 2
        ),
        reverse=True,
    )
    for customer_count, kind, value in shared[:5]:
        evidence.append(f"{customer_count} customers share {kind} {value}")

    failed = sum(e.event_type == "payment.failed" for e in tx_events)
    if tx_events:
        failure_rate = failed / len(tx_events)
        evidence.append(
            f"{failed}/{len(tx_events)} linked transactions failed ({failure_rate:.0%})"
        )
        start = min(e.timestamp for e in tx_events)
        end = max(e.timestamp for e in tx_events)
        span_minutes = max(0.0, (end - start).total_seconds() / 60.0)
        evidence.append(f"cluster activity spans {span_minutes:.1f} minutes")
    return {k: sorted(v) for k, v in entity_values.items()}, evidence, customers_by_entity


def _cluster_validation(
    tx_events: list[PaymentEvent],
    customers_by_entity: dict[tuple[str, str], set[str]],
    component_scores: list[float],
    model_threshold: float,
) -> dict[str, object]:
    customer_count = max(1, len({e.customer_id for e in tx_events}))
    failure_rate = sum(e.event_type == "payment.failed" for e in tx_events) / max(1, len(tx_events))

    max_shared: dict[str, int] = {}
    concentrations: list[float] = []
    for kind in ("device", "ip", "instrument"):
        values = [
            len(customers)
            for (entity_kind, _), customers in customers_by_entity.items()
            if entity_kind == kind
        ]
        maximum = max(values, default=0)
        max_shared[kind] = maximum
        concentrations.append(maximum / customer_count)

    entity_concentration = sum(concentrations) / len(concentrations)
    # "Strong shared" requires either 3 customers or 25% of the cluster,
    # whichever is larger. This prevents a huge diffuse network from looking
    # suspicious because a handful of customers happened to reuse one device.
    strong_share_min = max(3, int((customer_count * 0.25) + 0.9999))
    strong_shared_entity_types = sum(
        1 for maximum in max_shared.values() if maximum >= strong_share_min
    )

    mean_model_score = mean(component_scores) if component_scores else 0.0
    max_model_score = max(component_scores, default=0.0)
    model_flagged_event_ratio = (
        sum(score >= model_threshold for score in component_scores) / len(component_scores)
        if component_scores else 0.0
    )
    strong_event_threshold = max(CLUSTER_STRONG_EVENT_FLOOR, model_threshold)
    high_risk_event_ratio = (
        sum(score >= strong_event_threshold for score in component_scores) / len(component_scores)
        if component_scores else 0.0
    )

    # Cluster calibration intentionally down-weights the event-level operational
    # cutoff and rewards agreement between strong ML scores + concentrated entity
    # reuse. This makes a dense ring score high while a giant benign component
    # connected through occasional shared devices remains low.
    calibrated_risk = (
        0.45 * mean_model_score
        + 0.25 * high_risk_event_ratio
        + 0.20 * entity_concentration
        + 0.10 * failure_rate
    )
    calibrated_risk = min(0.99, max(0.0, calibrated_risk))

    if (
        calibrated_risk >= 0.65
        and strong_shared_entity_types >= 2
        and high_risk_event_ratio >= 0.50
        and mean_model_score >= 0.30
    ):
        classification = "HIGH_RISK_RING"
        risk_level = "high"
        recommended_action = "ESCALATE_REVIEW"
    elif (
        calibrated_risk >= 0.40
        and (strong_shared_entity_types >= 1 or high_risk_event_ratio >= 0.25)
        and mean_model_score >= 0.15
    ):
        classification = "SUSPICIOUS_CLUSTER"
        risk_level = "medium"
        recommended_action = "REVIEW"
    elif (
        mean_model_score < 0.12
        and high_risk_event_ratio < 0.10
        and entity_concentration < 0.20
    ):
        classification = "BENIGN_SHARED_NETWORK"
        risk_level = "low"
        recommended_action = "NO_ACTION"
    else:
        classification = "MONITOR"
        risk_level = "low"
        recommended_action = "MONITOR"

    validation_reasons = [
        f"mean event model score {mean_model_score:.3f}",
        f"{high_risk_event_ratio:.0%} of events exceed strong-risk threshold {strong_event_threshold:.2f}",
        f"entity concentration {entity_concentration:.0%} across device/IP/instrument",
        f"{strong_shared_entity_types}/3 entity types show concentrated reuse",
    ]

    return {
        "risk_score": round(calibrated_risk, 4),
        "classification": classification,
        "risk_level": risk_level,
        "mean_model_score": round(mean_model_score, 4) if component_scores else None,
        "max_model_score": round(max_model_score, 4) if component_scores else None,
        "model_flagged_event_ratio": round(model_flagged_event_ratio, 4),
        "high_risk_event_ratio": round(high_risk_event_ratio, 4),
        "failure_rate": round(failure_rate, 4),
        "entity_concentration": round(entity_concentration, 4),
        "strong_shared_entity_types": strong_shared_entity_types,
        "recommended_action": recommended_action,
        # Stage 3.1 remains observe/review-only. No cluster may execute money or
        # payment actions until detector validation is explicitly accepted.
        "action_allowed": False,
        "validation_reasons": validation_reasons,
    }


def cluster_summary(
    events: list[PaymentEvent],
    model_scores: dict[str, float] | None = None,
    model_threshold: float | None = None,
) -> list[RiskCluster]:
    association = build_association_graph(events)
    event_by_tx = {f"tx:{e.event_id}": e for e in events}
    clusters: list[RiskCluster] = []
    threshold = float(model_threshold if model_threshold is not None else 0.50)

    for idx, component in enumerate(nx.connected_components(association), start=1):
        tx_events = [event_by_tx[n] for n in component if n in event_by_tx]
        if len(tx_events) < 2:
            continue

        entities, evidence, customers_by_entity = _component_evidence(tx_events)
        component_scores = [
            float(model_scores[e.event_id])
            for e in tx_events
            if model_scores and e.event_id in model_scores
        ]

        if component_scores:
            validation = _cluster_validation(
                tx_events,
                customers_by_entity,
                component_scores,
                threshold,
            )
            risk = float(validation["risk_score"])
            detector = "risk-graph-ml+cluster-validation"
        else:
            # v0.3: the synthetic-trained ML artifact is intentionally retired.
            # Clusters are scored from deterministic graph evidence collected from
            # genuine Razorpay Test Mode transactions only. Nothing here can act.
            customers = max(1, len(set(entities.get("customer", []))))
            max_by_kind: dict[str, int] = {}
            concentrations: list[float] = []
            for kind in ("device", "ip", "instrument"):
                values = [
                    len(customer_set)
                    for (entity_kind, _), customer_set in customers_by_entity.items()
                    if entity_kind == kind
                ]
                maximum = max(values, default=0)
                max_by_kind[kind] = maximum
                concentrations.append(maximum / customers)
            entity_concentration = sum(concentrations) / 3.0
            strong_share_min = max(3, int((customers * 0.25) + 0.9999))
            strong_shared_entity_types = sum(
                1 for maximum in max_by_kind.values() if maximum >= strong_share_min
            )
            failure_rate = sum(e.event_type == "payment.failed" for e in tx_events) / len(tx_events)
            start = min(e.timestamp for e in tx_events)
            end = max(e.timestamp for e in tx_events)
            span_minutes = max(0.0, (end - start).total_seconds() / 60.0)
            if span_minutes <= 15:
                burst_score = 1.0
            elif span_minutes <= 60:
                burst_score = 0.7
            elif span_minutes <= 180:
                burst_score = 0.4
            else:
                burst_score = 0.1
            baseline_risk = min(
                0.99,
                0.35 * entity_concentration
                + 0.20 * (strong_shared_entity_types / 3.0)
                + 0.25 * failure_rate
                + 0.20 * burst_score,
            )
            risk = baseline_risk
            detector = "razorpay-testmode-graph-evidence"
            if (
                customers >= 5
                and strong_shared_entity_types >= 2
                and entity_concentration >= 0.50
                and baseline_risk >= 0.55
            ):
                classification = "HIGH_RISK_RING"
                risk_level = "high"
                recommended_action = "ESCALATE_REVIEW"
            elif strong_shared_entity_types >= 1 and baseline_risk >= 0.35:
                classification = "SUSPICIOUS_CLUSTER"
                risk_level = "medium"
                recommended_action = "REVIEW"
            elif entity_concentration < 0.15 and failure_rate < 0.15:
                classification = "BENIGN_SHARED_NETWORK"
                risk_level = "low"
                recommended_action = "NO_ACTION"
            else:
                classification = "MONITOR"
                risk_level = "low"
                recommended_action = "MONITOR"
            validation = {
                "classification": classification,
                "risk_level": risk_level,
                "mean_model_score": None,
                "max_model_score": None,
                "model_flagged_event_ratio": 0.0,
                "high_risk_event_ratio": 0.0,
                "failure_rate": round(failure_rate, 4),
                "entity_concentration": round(entity_concentration, 4),
                "strong_shared_entity_types": strong_shared_entity_types,
                "recommended_action": recommended_action,
                "action_allowed": False,
                "validation_reasons": [
                    "active ML model intentionally disabled until Razorpay Test Mode labels are collected",
                    f"entity concentration {entity_concentration:.0%} across device/IP/instrument",
                    f"{strong_shared_entity_types}/3 entity types show concentrated reuse",
                    f"failure rate {failure_rate:.0%}; activity span {span_minutes:.1f} minutes",
                ],
            }

        exposure = sum(e.amount for e in tx_events if e.event_type == "payment.failed")

        clusters.append(
            RiskCluster(
                cluster_id=f"cluster-{idx}",
                risk_score=round(risk, 4),
                members=len(tx_events),
                estimated_exposure=round(exposure, 2),
                entities=entities,
                evidence=evidence,
                detector=detector,
                mean_model_score=validation["mean_model_score"],
                max_model_score=validation["max_model_score"],
                model_flagged_event_ratio=float(validation["model_flagged_event_ratio"]),
                high_risk_event_ratio=float(validation["high_risk_event_ratio"]),
                failure_rate=float(validation["failure_rate"]),
                entity_concentration=float(validation["entity_concentration"]),
                strong_shared_entity_types=int(validation["strong_shared_entity_types"]),
                classification=str(validation["classification"]),
                risk_level=str(validation["risk_level"]),
                recommended_action=str(validation["recommended_action"]),
                action_allowed=bool(validation["action_allowed"]),
                validation_reasons=list(validation["validation_reasons"]),
            )
        )
    return sorted(
        clusters,
        key=lambda x: (x.risk_score, x.estimated_exposure),
        reverse=True,
    )


def customer_community_predictions(events: list[PaymentEvent]) -> dict[str, int]:
    """Unsupervised community-detection baseline mapped back to event IDs.

    It creates a customer projection using shared devices/IPs/instruments, applies
    greedy modularity communities, and flags communities with dense resource
    sharing and elevated failure rate. Labels are not used to form communities.
    """
    customer_graph = nx.Graph()
    entity_customers: dict[tuple[str, str], set[str]] = defaultdict(set)
    events_by_customer: dict[str, list[PaymentEvent]] = defaultdict(list)
    for e in events:
        events_by_customer[e.customer_id].append(e)
        customer_graph.add_node(e.customer_id)
        for kind, value in (
            ("device", e.device_id),
            ("ip", e.ip_address),
            ("instrument", e.instrument_id),
        ):
            if _valid_shared_entity(kind, value):
                entity_customers[(kind, value)].add(e.customer_id)

    for customers in entity_customers.values():
        if len(customers) < 2 or len(customers) > 80:
            continue
        items = sorted(customers)
        for i, left in enumerate(items):
            for right in items[i + 1:]:
                if customer_graph.has_edge(left, right):
                    customer_graph[left][right]["weight"] += 1
                else:
                    customer_graph.add_edge(left, right, weight=1)

    if customer_graph.number_of_edges() == 0:
        return {e.event_id: 0 for e in events}

    communities = list(
        nx.algorithms.community.greedy_modularity_communities(
            customer_graph,
            weight="weight",
        )
    )
    suspicious_customers: set[str] = set()
    for community in communities:
        if len(community) < 3:
            continue
        sub = customer_graph.subgraph(community)
        density = nx.density(sub)
        community_events = [
            e for customer in community for e in events_by_customer[customer]
        ]
        failure_rate = sum(
            e.event_type == "payment.failed" for e in community_events
        ) / max(1, len(community_events))
        shared_edge_weight = sum(
            d.get("weight", 1) for _, _, d in sub.edges(data=True)
        ) / max(1, sub.number_of_edges())
        if density >= 0.18 and shared_edge_weight >= 1.2 and failure_rate >= 0.30:
            suspicious_customers.update(community)

    return {
        e.event_id: int(e.customer_id in suspicious_customers)
        for e in events
    }
