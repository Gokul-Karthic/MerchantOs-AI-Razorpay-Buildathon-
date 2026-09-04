from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models.schemas import PaymentEvent


WEBHOOK_SOURCE = "razorpay_test_mode_webhook"
API_SYNC_SOURCE = "razorpay_test_mode_api_sync"


def _source_priority(source: str) -> int:
    if source == WEBHOOK_SOURCE:
        return 2
    if source == API_SYNC_SOURCE:
        return 1
    return 0


def _event_state_priority(event_type: str) -> int:
    # Razorpay webhook delivery can be out of order. Do not let a late
    # authorization observation downgrade a terminal captured/failed state.
    if event_type in {"payment.captured", "payment.failed"}:
        return 2
    if event_type == "payment.authorized":
        return 1
    return 0

def _default_db_path() -> Path:
    explicit = os.getenv("MERCHANTOS_DB_PATH", "").strip()
    if explicit:
        return Path(explicit).expanduser().resolve()
    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url.startswith("sqlite:///"):
        raw = database_url.removeprefix("sqlite:///")
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        return path.resolve()
    return Path(__file__).resolve().parents[2] / "merchantos.db"


DB_PATH = _default_db_path()


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    with connect() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            order_id TEXT NOT NULL,
            payment_id TEXT,
            customer_id TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            method TEXT NOT NULL,
            bank TEXT NOT NULL,
            device_id TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            instrument_id TEXT NOT NULL DEFAULT 'unknown',
            merchant_id TEXT NOT NULL DEFAULT 'merchant-test',
            timestamp TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'razorpay_test_mode',
            scenario_label TEXT NOT NULL DEFAULT 'UNLABELED',
            metadata TEXT NOT NULL
        )
        """)
        _ensure_column(conn, "events", "instrument_id", "TEXT NOT NULL DEFAULT 'unknown'")
        _ensure_column(conn, "events", "merchant_id", "TEXT NOT NULL DEFAULT 'merchant-test'")
        _ensure_column(conn, "events", "source", "TEXT NOT NULL DEFAULT 'legacy_unknown'")
        _ensure_column(conn, "events", "scenario_label", "TEXT NOT NULL DEFAULT 'UNLABELED'")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            audit_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            risk_score REAL NOT NULL,
            revenue_at_risk REAL NOT NULL,
            recommended_action TEXT NOT NULL,
            confidence REAL NOT NULL,
            reason TEXT NOT NULL,
            guardrail TEXT NOT NULL,
            simulation TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        _ensure_column(conn, "decisions", "guardrail_status", "TEXT NOT NULL DEFAULT 'SIMULATION_ONLY'")
        _ensure_column(conn, "decisions", "incident_id", "TEXT")
        _ensure_column(conn, "decisions", "approval_id", "TEXT")
        _ensure_column(conn, "decisions", "action_id", "TEXT")
        _ensure_column(conn, "decisions", "metadata", "TEXT NOT NULL DEFAULT '{}'")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS razorpay_order_contexts (
            order_id TEXT PRIMARY KEY,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            receipt TEXT,
            scenario_label TEXT NOT NULL,
            session_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            ip_address TEXT NOT NULL,
            customer_ref TEXT NOT NULL,
            merchant_id TEXT NOT NULL,
            provider_status TEXT,
            provider_payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS payment_journeys (
            journey_id TEXT PRIMARY KEY,
            order_id TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            customer_ref TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'AWAITING_PAYMENT',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS razorpay_webhook_events (
            webhook_event_id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            normalized_event_id TEXT,
            processing_error TEXT,
            received_at TEXT NOT NULL,
            processed_at TEXT
        )
        """)
        _ensure_column(conn, "razorpay_webhook_events", "normalized_event_id", "TEXT")
        _ensure_column(conn, "razorpay_webhook_events", "processing_error", "TEXT")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS payguard_incidents (
            incident_id TEXT PRIMARY KEY,
            status TEXT NOT NULL, severity TEXT NOT NULL, scope TEXT NOT NULL,
            method TEXT NOT NULL, bank TEXT NOT NULL, recent_transactions INTEGER NOT NULL,
            recent_failures INTEGER NOT NULL, recent_failure_rate REAL NOT NULL,
            baseline_failure_rate REAL NOT NULL, degradation REAL NOT NULL,
            revenue_at_risk REAL NOT NULL, root_cause TEXT NOT NULL, evidence TEXT NOT NULL,
            window_start TEXT NOT NULL, window_end TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS approvals (
            approval_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, event_id TEXT NOT NULL,
            action_type TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
            note TEXT, created_at TEXT NOT NULL, decided_at TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS actions (
            action_id TEXT PRIMARY KEY, audit_id TEXT NOT NULL, event_id TEXT NOT NULL,
            action_type TEXT NOT NULL, execution_mode TEXT NOT NULL, status TEXT NOT NULL,
            provider_entity_type TEXT, provider_entity_id TEXT, provider_payload TEXT NOT NULL,
            expected_recovery REAL NOT NULL DEFAULT 0, actual_recovery REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, executed_at TEXT, verified_at TEXT, error TEXT
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_events (
            seq INTEGER PRIMARY KEY AUTOINCREMENT, audit_event_id TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL, entity_id TEXT NOT NULL, event_type TEXT NOT NULL,
            payload TEXT NOT NULL, prev_hash TEXT NOT NULL, event_hash TEXT NOT NULL, created_at TEXT NOT NULL
        )
        """)
        conn.commit()


def clear_non_razorpay_events() -> int:
    """Remove legacy non-Test-Mode event rows from a reused local database."""
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM events WHERE source NOT LIKE 'razorpay_test_mode%'"
        )
        conn.commit()
        return cur.rowcount


def _merge_event(existing: PaymentEvent | None, incoming: PaymentEvent) -> PaymentEvent:
    now = datetime.now(timezone.utc).isoformat()
    existing_metadata = dict(existing.metadata) if existing else {}
    incoming_metadata = dict(incoming.metadata)

    sources = list(existing_metadata.get("ingestion_sources") or [])
    if existing and existing.source not in sources:
        sources.append(existing.source)
    if incoming.source not in sources:
        sources.append(incoming.source)

    webhook_seen = (
        (existing is not None and existing.source == WEBHOOK_SOURCE)
        or incoming.source == WEBHOOK_SOURCE
        or bool(existing_metadata.get("webhook_verified"))
    )
    api_seen = (
        (existing is not None and existing.source == API_SYNC_SOURCE)
        or incoming.source == API_SYNC_SOURCE
        or bool(existing_metadata.get("api_verified"))
    )
    primary_source = WEBHOOK_SOURCE if webhook_seen else (
        API_SYNC_SOURCE if api_seen else max(
            [src for src in sources if isinstance(src, str)],
            key=_source_priority,
            default=incoming.source,
        )
    )

    incoming_is_stale = bool(
        existing
        and _event_state_priority(incoming.event_type) < _event_state_priority(existing.event_type)
    )

    # Incoming provider fields are authoritative unless the delivery is a
    # known lower-state observation arriving after a terminal state.
    metadata = {**existing_metadata, **incoming_metadata}
    if incoming_is_stale and existing:
        for key in (
            "provider_status", "error_code", "error_description", "error_source",
            "error_step", "error_reason",
        ):
            if key in existing_metadata:
                metadata[key] = existing_metadata[key]

    metadata.update({
        "primary_ingestion_source": primary_source,
        "ingestion_sources": sources,
        "webhook_verified": webhook_seen,
        "api_verified": api_seen,
        "first_ingested_at": existing_metadata.get("first_ingested_at", now),
        "last_ingested_at": now,
        "last_ingestion_source": incoming.source,
    })
    if incoming.source == WEBHOOK_SOURCE:
        metadata["last_webhook_event_type"] = incoming.event_type
        metadata["last_webhook_received_at"] = now
    if incoming.source == API_SYNC_SOURCE:
        metadata["last_api_verified_at"] = now

    if not existing:
        return incoming.model_copy(update={"source": primary_source, "metadata": metadata})

    event_type = existing.event_type if incoming_is_stale else incoming.event_type
    scenario_label = (
        existing.scenario_label
        if existing.scenario_label != "UNLABELED" and incoming.scenario_label == "UNLABELED"
        else incoming.scenario_label
    )

    def prefer_known(new_value: str, old_value: str) -> str:
        return old_value if new_value in {"", "unknown", "None"} and old_value not in {"", "unknown", "None"} else new_value

    return incoming.model_copy(update={
        "event_type": event_type,
        "source": primary_source,
        "scenario_label": scenario_label,
        "customer_id": prefer_known(incoming.customer_id, existing.customer_id),
        "device_id": prefer_known(incoming.device_id, existing.device_id),
        "ip_address": prefer_known(incoming.ip_address, existing.ip_address),
        "instrument_id": prefer_known(incoming.instrument_id, existing.instrument_id),
        "merchant_id": prefer_known(incoming.merchant_id, existing.merchant_id),
        "metadata": metadata,
    })


def upsert_event(event: PaymentEvent) -> PaymentEvent:
    if not event.source.startswith("razorpay_test_mode"):
        raise ValueError("MerchantOS v1.4.1 only accepts Razorpay Test Mode events")
    existing = get_event(event.event_id)
    merged = _merge_event(existing, event)
    with connect() as conn:
        conn.execute("""
        INSERT INTO events (
            event_id, event_type, order_id, payment_id, customer_id, amount,
            currency, method, bank, device_id, ip_address, instrument_id,
            merchant_id, timestamp, source, scenario_label, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(event_id) DO UPDATE SET
            event_type=excluded.event_type,
            order_id=excluded.order_id,
            payment_id=excluded.payment_id,
            customer_id=excluded.customer_id,
            amount=excluded.amount,
            currency=excluded.currency,
            method=excluded.method,
            bank=excluded.bank,
            device_id=excluded.device_id,
            ip_address=excluded.ip_address,
            instrument_id=excluded.instrument_id,
            merchant_id=excluded.merchant_id,
            timestamp=excluded.timestamp,
            source=excluded.source,
            scenario_label=excluded.scenario_label,
            metadata=excluded.metadata
        """, (
            merged.event_id, merged.event_type, merged.order_id, merged.payment_id,
            merged.customer_id, merged.amount, merged.currency, merged.method,
            merged.bank, merged.device_id, merged.ip_address, merged.instrument_id,
            merged.merchant_id, merged.timestamp.isoformat(), merged.source,
            merged.scenario_label, json.dumps(merged.metadata),
        ))
        conn.commit()
    return merged


def _row_to_event(row: sqlite3.Row) -> PaymentEvent:
    keys = set(row.keys())
    return PaymentEvent(
        event_id=row["event_id"], event_type=row["event_type"], order_id=row["order_id"],
        payment_id=row["payment_id"], customer_id=row["customer_id"], amount=row["amount"],
        currency=row["currency"], method=row["method"], bank=row["bank"],
        device_id=row["device_id"], ip_address=row["ip_address"],
        instrument_id=row["instrument_id"] if "instrument_id" in keys else "unknown",
        merchant_id=row["merchant_id"] if "merchant_id" in keys else "merchant-test",
        timestamp=row["timestamp"],
        source=row["source"] if "source" in keys else "legacy_unknown",
        scenario_label=row["scenario_label"] if "scenario_label" in keys else "UNLABELED",
        metadata=json.loads(row["metadata"]),
    )


def get_event(event_id: str) -> PaymentEvent | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    return _row_to_event(row) if row else None


def list_events() -> list[PaymentEvent]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE source LIKE 'razorpay_test_mode%' ORDER BY timestamp DESC"
        ).fetchall()
    return [_row_to_event(r) for r in rows]


def save_order_context(
    *,
    order: dict[str, Any],
    scenario_label: str,
    session_id: str,
    device_id: str,
    ip_address: str,
    customer_ref: str,
    merchant_id: str = "merchant-test",
) -> None:
    with connect() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO razorpay_order_contexts (
            order_id, amount, currency, receipt, scenario_label, session_id,
            device_id, ip_address, customer_ref, merchant_id, provider_status,
            provider_payload, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["id"], float(order.get("amount", 0)) / 100.0,
            str(order.get("currency") or "INR"), order.get("receipt"), scenario_label,
            session_id, device_id, ip_address, customer_ref, merchant_id,
            order.get("status"), json.dumps(order),
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()


def get_order_context(order_id: str | None) -> dict[str, Any] | None:
    if not order_id:
        return None
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM razorpay_order_contexts WHERE order_id = ?", (order_id,)
        ).fetchone()
    return dict(row) if row else None


def list_order_contexts(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM razorpay_order_contexts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def save_journey(
    *,
    journey_id: str,
    order_id: str,
    amount: float,
    currency: str,
    customer_ref: str,
    description: str | None = None,
    status: str = "AWAITING_PAYMENT",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO payment_journeys (
                journey_id, order_id, amount, currency, customer_ref, description,
                status, metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (journey_id, order_id, float(amount), currency, customer_ref, description,
             status, json.dumps(metadata or {}), now, now),
        )
        conn.commit()
    return get_journey(journey_id) or {}


def _journey_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["metadata"] = json.loads(data.get("metadata") or "{}")
    except (TypeError, json.JSONDecodeError):
        data["metadata"] = {}
    return data


def get_journey(journey_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM payment_journeys WHERE journey_id=?", (journey_id,)
        ).fetchone()
    return _journey_row(row) if row else None


def get_journey_by_order(order_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM payment_journeys WHERE order_id=?", (order_id,)
        ).fetchone()
    return _journey_row(row) if row else None


def list_journeys(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM payment_journeys ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_journey_row(row) for row in rows]


def update_journey(journey_id: str, **updates: Any) -> dict[str, Any] | None:
    allowed = {"status", "description", "metadata"}
    clean = {k: v for k, v in updates.items() if k in allowed}
    if not clean:
        return get_journey(journey_id)
    if "metadata" in clean:
        clean["metadata"] = json.dumps(clean["metadata"] or {})
    clean["updated_at"] = datetime.now(timezone.utc).isoformat()
    sql = ", ".join(f"{key}=?" for key in clean)
    with connect() as conn:
        conn.execute(
            f"UPDATE payment_journeys SET {sql} WHERE journey_id=?",
            (*clean.values(), journey_id),
        )
        conn.commit()
    return get_journey(journey_id)


def list_events_for_order(order_id: str) -> list[PaymentEvent]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE order_id=? AND source LIKE 'razorpay_test_mode%' ORDER BY timestamp ASC",
            (order_id,),
        ).fetchall()
    return [_row_to_event(row) for row in rows]


def list_webhook_events_for_event_ids(event_ids: list[str]) -> list[dict[str, Any]]:
    if not event_ids:
        return []
    placeholders = ",".join("?" for _ in event_ids)
    with connect() as conn:
        rows = conn.execute(
            f"""SELECT webhook_event_id,event_type,processed,normalized_event_id,
                       processing_error,received_at,processed_at
                FROM razorpay_webhook_events
                WHERE normalized_event_id IN ({placeholders})
                ORDER BY received_at ASC""",
            tuple(event_ids),
        ).fetchall()
    return [dict(row) for row in rows]


def list_decisions_for_event(event_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE event_id=? ORDER BY created_at ASC", (event_id,)
        ).fetchall()
    return [_decision_row(row) for row in rows]


def list_actions_for_event(event_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM actions WHERE event_id=? ORDER BY created_at ASC", (event_id,)
        ).fetchall()
    return [_action_row(row) for row in rows]


def list_approvals_for_event(event_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM approvals WHERE event_id=? ORDER BY created_at ASC", (event_id,)
        ).fetchall()
    return [dict(row) for row in rows]


def list_audit_events_for_entities(entity_pairs: list[tuple[str, str]], limit: int = 500) -> list[dict[str, Any]]:
    if not entity_pairs:
        return []
    clauses = " OR ".join("(entity_type=? AND entity_id=?)" for _ in entity_pairs)
    params: list[Any] = []
    for entity_type, entity_id in entity_pairs:
        params.extend([entity_type, entity_id])
    params.append(limit)
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM audit_events WHERE {clauses} ORDER BY seq ASC LIMIT ?", tuple(params)
        ).fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        data = dict(row)
        try:
            data["payload"] = json.loads(data.get("payload") or "{}")
        except (TypeError, json.JSONDecodeError):
            pass
        out.append(data)
    return out


def claim_webhook_event(webhook_event_id: str, event_type: str, payload_sha256: str) -> bool:
    with connect() as conn:
        cur = conn.execute("""
        INSERT OR IGNORE INTO razorpay_webhook_events (
            webhook_event_id, event_type, payload_sha256, received_at
        ) VALUES (?, ?, ?, ?)
        """, (
            webhook_event_id,
            event_type,
            payload_sha256,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
        return cur.rowcount == 1


def mark_webhook_processed(
    webhook_event_id: str,
    *,
    normalized_event_id: str | None = None,
    processing_error: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute("""
        UPDATE razorpay_webhook_events
        SET processed = ?, normalized_event_id = ?, processing_error = ?, processed_at = ?
        WHERE webhook_event_id = ?
        """, (
            0 if processing_error else 1,
            normalized_event_id,
            processing_error,
            datetime.now(timezone.utc).isoformat(),
            webhook_event_id,
        ))
        conn.commit()


def list_webhook_events(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("""
        SELECT webhook_event_id, event_type, processed, normalized_event_id,
               processing_error, received_at, processed_at
        FROM razorpay_webhook_events
        ORDER BY received_at DESC
        LIMIT ?
        """, (limit,)).fetchall()
    return [dict(row) for row in rows]


def webhook_stats() -> dict[str, int]:
    with connect() as conn:
        row = conn.execute("""
        SELECT COUNT(*) AS total, SUM(processed) AS processed
        FROM razorpay_webhook_events
        """).fetchone()
    return {"total": int(row["total"] or 0), "processed": int(row["processed"] or 0)}


def dataset_status() -> dict[str, Any]:
    with connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM events WHERE source LIKE 'razorpay_test_mode%'"
        ).fetchone()["n"]
        labels = conn.execute("""
        SELECT scenario_label, COUNT(*) AS n
        FROM events
        WHERE source LIKE 'razorpay_test_mode%'
        GROUP BY scenario_label
        ORDER BY scenario_label
        """).fetchall()
        methods = conn.execute("""
        SELECT method, COUNT(*) AS n
        FROM events
        WHERE source LIKE 'razorpay_test_mode%'
        GROUP BY method
        ORDER BY n DESC
        """).fetchall()
    try:
        from app.ml.risk_model import model_status
        ms = model_status(list_events())
        learned_active = bool(ms.get("learned_calibrator_active"))
        operational_active = bool(ms.get("active", True))
    except Exception:
        learned_active = False
        operational_active = True
    return {
        "total_test_mode_payments": int(total),
        "scenario_labels": {row["scenario_label"]: int(row["n"]) for row in labels},
        "methods": {row["method"]: int(row["n"]) for row in methods},
        "active_ml_model": learned_active,
        "operational_risknet_active": operational_active,
        "ml_training_policy": "one-time finalization from existing controlled Razorpay Test Mode labels; artifact locked by default",
    }


def save_decision(audit_id: str, result: dict) -> None:
    metadata = {
        "digital_twin": result.get("digital_twin", []),
        "learned_risk_score": result.get("learned_risk_score"),
        "deterministic_risk_score": result.get("deterministic_risk_score"),
    }
    with connect() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO decisions (
            audit_id, event_id, risk_score, revenue_at_risk, recommended_action,
            confidence, reason, guardrail, simulation, created_at, guardrail_status,
            incident_id, approval_id, action_id, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            audit_id, result["event_id"], result["risk_score"], result["revenue_at_risk"],
            result["recommended_action"], result["confidence"], result["reason"],
            result["guardrail"], json.dumps(result.get("simulation", {})),
            datetime.now(timezone.utc).isoformat(), result.get("guardrail_status", "SIMULATION_ONLY"),
            result.get("incident_id"), result.get("approval_id"), result.get("action_id"),
            json.dumps(metadata),
        ))
        conn.commit()


def update_decision_links(audit_id: str, *, approval_id: str | None = None, action_id: str | None = None) -> None:
    with connect() as conn:
        if approval_id is not None:
            conn.execute("UPDATE decisions SET approval_id=? WHERE audit_id=?", (approval_id, audit_id))
        if action_id is not None:
            conn.execute("UPDATE decisions SET action_id=? WHERE audit_id=?", (action_id, audit_id))
        conn.commit()


def get_decision(audit_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE audit_id=?", (audit_id,)).fetchone()
    return _decision_row(row) if row else None


def latest_decision_for_event(event_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM decisions WHERE event_id=? ORDER BY created_at DESC LIMIT 1", (event_id,)).fetchone()
    return _decision_row(row) if row else None


def _decision_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in ("simulation", "metadata"):
        try:
            data[key] = json.loads(data.get(key) or "{}")
        except (TypeError, json.JSONDecodeError):
            data[key] = {}
    return data


def list_decisions(limit: int = 100) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [_decision_row(r) for r in rows]


def save_incidents(incidents: list[Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    active_ids = [incident.incident_id if hasattr(incident, "incident_id") else dict(incident)["incident_id"] for incident in incidents]
    with connect() as conn:
        if active_ids:
            placeholders = ",".join("?" for _ in active_ids)
            conn.execute(f"UPDATE payguard_incidents SET status='RESOLVED', updated_at=? WHERE status!='RESOLVED' AND incident_id NOT IN ({placeholders})", (now, *active_ids))
        else:
            conn.execute("UPDATE payguard_incidents SET status='RESOLVED', updated_at=? WHERE status!='RESOLVED'", (now,))
        for incident in incidents:
            d = incident.model_dump(mode="json") if hasattr(incident, "model_dump") else dict(incident)
            conn.execute("""
            INSERT INTO payguard_incidents (
                incident_id,status,severity,scope,method,bank,recent_transactions,recent_failures,
                recent_failure_rate,baseline_failure_rate,degradation,revenue_at_risk,root_cause,evidence,
                window_start,window_end,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(incident_id) DO UPDATE SET
                status=excluded.status,severity=excluded.severity,scope=excluded.scope,method=excluded.method,
                bank=excluded.bank,recent_transactions=excluded.recent_transactions,recent_failures=excluded.recent_failures,
                recent_failure_rate=excluded.recent_failure_rate,baseline_failure_rate=excluded.baseline_failure_rate,
                degradation=excluded.degradation,revenue_at_risk=excluded.revenue_at_risk,root_cause=excluded.root_cause,
                evidence=excluded.evidence,window_start=excluded.window_start,window_end=excluded.window_end,updated_at=excluded.updated_at
            """, (
                d["incident_id"],d["status"],d["severity"],d["scope"],d["method"],d["bank"],d["recent_transactions"],
                d["recent_failures"],d["recent_failure_rate"],d["baseline_failure_rate"],d["degradation"],d["revenue_at_risk"],
                d["root_cause"],json.dumps(d.get("evidence",[])),str(d["window_start"]),str(d["window_end"]),now,now,
            ))
        conn.commit()


def list_incidents(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM payguard_incidents ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
    out=[]
    for row in rows:
        d=dict(row); d["evidence"]=json.loads(d.get("evidence") or "[]"); out.append(d)
    return out


def create_approval(approval_id: str, audit_id: str, event_id: str, action_type: str, reason: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO approvals VALUES (?,?,?,?,?,?,?,?,?)", (
            approval_id,audit_id,event_id,action_type,"PENDING",reason,None,datetime.now(timezone.utc).isoformat(),None,
        )); conn.commit()


def decide_approval(approval_id: str, approved: bool, note: str | None = None) -> dict[str, Any] | None:
    status="APPROVED" if approved else "REJECTED"
    with connect() as conn:
        conn.execute("UPDATE approvals SET status=?, note=?, decided_at=? WHERE approval_id=?", (
            status,note,datetime.now(timezone.utc).isoformat(),approval_id,
        )); conn.commit()
    return get_approval(approval_id)


def get_approval(approval_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row=conn.execute("SELECT * FROM approvals WHERE approval_id=?",(approval_id,)).fetchone()
    return dict(row) if row else None


def list_approvals(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows=conn.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    return [dict(r) for r in rows]


def save_action(action: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO actions (
            action_id,audit_id,event_id,action_type,execution_mode,status,provider_entity_type,
            provider_entity_id,provider_payload,expected_recovery,actual_recovery,created_at,executed_at,verified_at,error
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            action["action_id"],action["audit_id"],action["event_id"],action["action_type"],action["execution_mode"],
            action["status"],action.get("provider_entity_type"),action.get("provider_entity_id"),
            json.dumps(action.get("provider_payload") or {}),float(action.get("expected_recovery",0)),float(action.get("actual_recovery",0)),
            action.get("created_at") or datetime.now(timezone.utc).isoformat(),action.get("executed_at"),action.get("verified_at"),action.get("error"),
        )); conn.commit()


def update_action(action_id: str, **updates: Any) -> dict[str, Any] | None:
    if not updates: return get_action(action_id)
    allowed={"status","provider_entity_type","provider_entity_id","provider_payload","expected_recovery","actual_recovery","executed_at","verified_at","error"}
    clean={k:v for k,v in updates.items() if k in allowed}
    if "provider_payload" in clean: clean["provider_payload"]=json.dumps(clean["provider_payload"] or {})
    if not clean: return get_action(action_id)
    sql=", ".join(f"{k}=?" for k in clean)
    with connect() as conn:
        conn.execute(f"UPDATE actions SET {sql} WHERE action_id=?",(*clean.values(),action_id)); conn.commit()
    return get_action(action_id)


def _action_row(row: sqlite3.Row) -> dict[str, Any]:
    d=dict(row)
    try: d["provider_payload"]=json.loads(d.get("provider_payload") or "{}")
    except (TypeError,json.JSONDecodeError): d["provider_payload"]={}
    return d


def get_action(action_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row=conn.execute("SELECT * FROM actions WHERE action_id=?",(action_id,)).fetchone()
    return _action_row(row) if row else None


def find_action_by_provider_id(provider_entity_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row=conn.execute("SELECT * FROM actions WHERE provider_entity_id=? ORDER BY created_at DESC LIMIT 1",(provider_entity_id,)).fetchone()
    return _action_row(row) if row else None


def list_actions(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows=conn.execute("SELECT * FROM actions ORDER BY created_at DESC LIMIT ?",(limit,)).fetchall()
    return [_action_row(r) for r in rows]


def append_audit(entity_type: str, entity_id: str, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    import hashlib, uuid
    created_at=datetime.now(timezone.utc).isoformat()
    canonical=json.dumps(payload,sort_keys=True,separators=(",",":"),default=str)
    with connect() as conn:
        last=conn.execute("SELECT event_hash FROM audit_events ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash=last["event_hash"] if last else "GENESIS"
        event_hash=hashlib.sha256(f"{prev_hash}|{entity_type}|{entity_id}|{event_type}|{canonical}|{created_at}".encode()).hexdigest()
        audit_event_id=f"ae-{uuid.uuid4().hex[:16]}"
        conn.execute("INSERT INTO audit_events (audit_event_id,entity_type,entity_id,event_type,payload,prev_hash,event_hash,created_at) VALUES (?,?,?,?,?,?,?,?)",(
            audit_event_id,entity_type,entity_id,event_type,canonical,prev_hash,event_hash,created_at,
        )); conn.commit()
    return {"audit_event_id":audit_event_id,"event_hash":event_hash,"prev_hash":prev_hash,"created_at":created_at}


def list_audit_events(limit: int = 200) -> list[dict[str, Any]]:
    with connect() as conn:
        rows=conn.execute("SELECT * FROM audit_events ORDER BY seq DESC LIMIT ?",(limit,)).fetchall()
    out=[]
    for r in rows:
        d=dict(r)
        try:d["payload"]=json.loads(d["payload"])
        except Exception: pass
        out.append(d)
    return out


def verify_audit_chain() -> dict[str, Any]:
    import hashlib
    with connect() as conn:
        rows=conn.execute("SELECT * FROM audit_events ORDER BY seq ASC").fetchall()
    prev="GENESIS"
    for row in rows:
        if row["prev_hash"] != prev:
            return {"valid":False,"checked":row["seq"]-1,"broken_at_seq":row["seq"],"reason":"prev_hash mismatch"}
        expected=hashlib.sha256(f'{prev}|{row["entity_type"]}|{row["entity_id"]}|{row["event_type"]}|{row["payload"]}|{row["created_at"]}'.encode()).hexdigest()
        if expected != row["event_hash"]:
            return {"valid":False,"checked":row["seq"]-1,"broken_at_seq":row["seq"],"reason":"event_hash mismatch"}
        prev=row["event_hash"]
    return {"valid":True,"checked":len(rows),"head_hash":prev}
