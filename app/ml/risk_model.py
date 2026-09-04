from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.model_selection import TimeSeriesSplit

from app.ml.risk_hybrid_features import CATEGORICAL_FEATURES, NUMERIC_FEATURES, identity_quality, temporal_behavior_features
from app.models.schemas import PaymentEvent


ROOT = Path(__file__).resolve().parents[2]
_ARTIFACT_DIR_RAW = os.getenv("MERCHANTOS_ARTIFACT_DIR", "").strip()
ARTIFACT_DIR = Path(_ARTIFACT_DIR_RAW).expanduser() if _ARTIFACT_DIR_RAW else ROOT / "artifacts"
if not ARTIFACT_DIR.is_absolute():
    ARTIFACT_DIR = (ROOT / ARTIFACT_DIR).resolve()
MODEL_PATH = ARTIFACT_DIR / "risknet_hybrid_v2.joblib"
METRICS_PATH = ARTIFACT_DIR / "risknet_hybrid_v2_manifest.json"
MODEL_VERSION = "risknet-hybrid-v2"
CRITICAL_RISK_THRESHOLD = 0.85


def dataset_readiness(events: list[PaymentEvent]) -> dict[str, Any]:
    labeled = [e for e in events if e.scenario_label != "UNLABELED"]
    abuse = [e for e in labeled if e.scenario_label == "CONTROLLED_ABUSE"]
    benign = [e for e in labeled if e.scenario_label in {"NORMAL", "LEGIT_SHARED_NETWORK"}]
    methods = {e.method for e in labeled if e.method != "unknown"}
    customers = {e.customer_id for e in labeled}
    sources_ok = all(e.source.startswith("razorpay_test_mode") for e in labeled)
    span_minutes = 0.0
    if len(labeled) >= 2:
        span_minutes = (max(e.timestamp for e in labeled) - min(e.timestamp for e in labeled)).total_seconds() / 60.0
    checks = {
        "test_mode_only": sources_ok,
        "labeled_events_at_least_50": len(labeled) >= 50,
        "controlled_abuse_at_least_12": len(abuse) >= 12,
        "benign_at_least_25": len(benign) >= 25,
        "payment_methods_at_least_2": len(methods) >= 2,
        "customers_at_least_10": len(customers) >= 10,
        "temporal_span_at_least_60m": span_minutes >= 60,
    }
    return {
        "ready": all(checks.values()),
        "checks": checks,
        "counts": {
            "labeled": len(labeled), "controlled_abuse": len(abuse), "benign": len(benign),
            "methods": len(methods), "customers": len(customers), "temporal_span_minutes": round(span_minutes, 1),
        },
        "policy": "Only genuine Razorpay Test Mode events with controlled experiment labels may fit RiskNet.",
    }


def _metrics(y_true: np.ndarray, prob: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = (prob >= threshold).astype(int)
    cm = confusion_matrix(y_true, pred, labels=[0, 1]).tolist()
    prevalence = float(np.mean(y_true)) if len(y_true) else 0.0
    out: dict[str, Any] = {
        "threshold": round(float(threshold), 4),
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "confusion_matrix": cm,
        "prevalence_baseline_pr_auc": round(prevalence, 4),
        "predicted_positive_rate": round(float(np.mean(pred)), 4),
    }
    if len(set(y_true.tolist())) > 1:
        pr = float(average_precision_score(y_true, prob))
        roc = float(roc_auc_score(y_true, prob))
        out["pr_auc"] = round(pr, 4)
        out["roc_auc"] = round(roc, 4)
        out["pr_auc_lift_vs_baseline"] = round(pr / prevalence, 4) if prevalence > 0 else None
    else:
        out.update({"pr_auc": None, "roc_auc": None, "pr_auc_lift_vs_baseline": None})
    return out


def _build_pipeline() -> Pipeline:
    preprocess = ColumnTransformer([
        ("num", StandardScaler(), NUMERIC_FEATURES),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=2), CATEGORICAL_FEATURES),
    ])
    model = LogisticRegression(C=0.35, class_weight="balanced", max_iter=3000, solver="liblinear", random_state=42)
    return Pipeline([("prep", preprocess), ("model", model)])


def _choose_threshold(y: np.ndarray, prob: np.ndarray) -> float:
    best = (0.85, -1.0)
    for t in np.arange(0.30, 0.901, 0.02):
        pred = (prob >= t).astype(int)
        if pred.min() == pred.max():
            continue
        precision = precision_score(y, pred, zero_division=0)
        recall = recall_score(y, pred, zero_division=0)
        # Safety-first but avoids the v1 all-positive failure mode.
        score = 0.55 * recall + 0.45 * precision
        if precision >= 0.35 and recall >= 0.50 and score > best[1]:
            best = (float(t), float(score))
    return best[0]


def _quality_gate(metrics: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    cm = metrics.get("confusion_matrix") or [[0, 0], [0, 0]]
    tn, fp = cm[0]
    fn, tp = cm[1]
    if tn < 1 or tp < 1:
        reasons.append("holdout must contain at least one true negative and one true positive")
    if metrics.get("roc_auc") is None or metrics["roc_auc"] < 0.60:
        reasons.append("holdout ROC-AUC below 0.60")
    lift = metrics.get("pr_auc_lift_vs_baseline")
    if lift is None or lift < 1.15:
        reasons.append("holdout PR-AUC does not beat prevalence baseline by at least 15%")
    if metrics.get("precision", 0) < 0.40:
        reasons.append("holdout precision below 0.40")
    if metrics.get("recall", 0) < 0.50:
        reasons.append("holdout recall below 0.50")
    ppr = metrics.get("predicted_positive_rate", 0)
    if ppr <= 0.02 or ppr >= 0.98:
        reasons.append("degenerate all-positive/all-negative prediction behavior")
    return (not reasons), reasons


def _reputation_tables(events: list[PaymentEvent]) -> dict[str, Any]:
    customers: dict[str, list[int]] = {}
    instruments: dict[str, list[int]] = {}
    for e in sorted(events, key=lambda x: (x.timestamp, x.event_id)):
        if e.scenario_label == "UNLABELED":
            continue
        label = int(e.scenario_label == "CONTROLLED_ABUSE")
        c = customers.setdefault(e.customer_id, [0, 0])
        c[0] += label; c[1] += 1
        if e.instrument_id not in {"", "unknown"}:
            i = instruments.setdefault(e.instrument_id, [0, 0])
            i[0] += label; i[1] += 1
    def table(src: dict[str, list[int]]) -> dict[str, dict[str, float | int]]:
        return {
            k: {"abuse": v[0], "total": v[1], "posterior": round((v[0] + 1.0) / (v[1] + 4.0), 6)}
            for k, v in src.items()
        }
    return {"customers": table(customers), "instruments": table(instruments)}


def train_testmode_model(events: list[PaymentEvent], *, activate: bool = True) -> dict[str, Any]:
    if MODEL_PATH.exists() and os.getenv("MERCHANTOS_ALLOW_MODEL_REFIT", "false").lower() != "true":
        return model_status(events)
    readiness = dataset_readiness(events)
    if not readiness["ready"]:
        raise ValueError("Razorpay Test Mode dataset is not ready for RiskNet finalization")

    frame = temporal_behavior_features(events)
    frame = frame[frame["label"] >= 0].sort_values(["timestamp", "event_id"]).reset_index(drop=True)
    n = len(frame)
    test_start = max(1, int(n * 0.80))
    dev, test = frame.iloc[:test_start].copy(), frame.iloc[test_start:].copy()
    if dev["label"].nunique() < 2 or test["label"].nunique() < 2:
        raise ValueError("chronological development and holdout partitions must each contain both classes")

    # Expanding-window OOF predictions pick threshold without peeking at final holdout.
    splitter = TimeSeriesSplit(n_splits=4)
    oof_y: list[int] = []
    oof_prob: list[float] = []
    cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    for tr_idx, va_idx in splitter.split(dev):
        tr, va = dev.iloc[tr_idx], dev.iloc[va_idx]
        if tr["label"].nunique() < 2 or va["label"].nunique() < 2:
            continue
        pipe = _build_pipeline()
        pipe.fit(tr[cols], tr["label"])
        oof_y.extend(va["label"].astype(int).tolist())
        oof_prob.extend(pipe.predict_proba(va[cols])[:, 1].tolist())
    threshold = _choose_threshold(np.array(oof_y, dtype=int), np.array(oof_prob, dtype=float)) if oof_y else 0.85
    validation_metrics = _metrics(np.array(oof_y, dtype=int), np.array(oof_prob, dtype=float), threshold) if oof_y else {
        "threshold": threshold, "precision": 0.0, "recall": 0.0, "f1": 0.0,
        "confusion_matrix": [[0, 0], [0, 0]], "prevalence_baseline_pr_auc": None,
        "predicted_positive_rate": 0.0, "pr_auc": None, "roc_auc": None, "pr_auc_lift_vs_baseline": None,
    }

    pipeline = _build_pipeline()
    pipeline.fit(dev[cols], dev["label"])
    test_prob = pipeline.predict_proba(test[cols])[:, 1]
    test_metrics = _metrics(test["label"].to_numpy(dtype=int), test_prob, threshold)
    calibrator_passed, reasons = _quality_gate(test_metrics)

    manifest: dict[str, Any] = {
        "trained": True,
        "active": bool(activate),
        "model_version": MODEL_VERSION,
        "model_type": "hybrid_policy_bayesian_reputation_optional_logistic_calibrator",
        "data_source": "razorpay_test_mode_only",
        "label_source": "controlled_test_mode_experiments",
        "locked": True,
        "refit_policy": "disabled_by_default",
        "no_additional_payments_required": True,
        "review_threshold": threshold,
        "critical_risk_threshold": CRITICAL_RISK_THRESHOLD,
        "development_rows": len(dev),
        "holdout_rows": len(test),
        "validation": validation_metrics,
        "test": test_metrics,
        "holdout": test_metrics,
        "learned_calibrator_active": bool(activate and calibrator_passed),
        "learned_calibrator_quality_gate_passed": calibrator_passed,
        "learned_calibrator_rejection_reasons": reasons,
        "identity_quality": identity_quality(events),
        "readiness_at_training": readiness,
        "safety": {
            "no_synthetic_rows": True,
            "no_live_mode_rows": True,
            "current_event_label_never_used_as_feature": True,
            "collapsed_local_device_ip_suppressed_from_learned_model": True,
            "action_execution_directly_from_model": False,
        },
    }
    bundle = {
        "pipeline": pipeline if calibrator_passed else None,
        "reputation": _reputation_tables(events),
        "manifest": manifest,
        "feature_columns": cols,
    }
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def ensure_production_model(events: list[PaymentEvent]) -> dict[str, Any]:
    if MODEL_PATH.exists():
        return model_status(events)
    readiness = dataset_readiness(events)
    refit_allowed = os.getenv("MERCHANTOS_ALLOW_MODEL_REFIT", "false").lower() == "true"
    if readiness["ready"] and refit_allowed:
        return train_testmode_model(events, activate=True)
    return {
        "trained": False,
        "active": True,
        "model_version": MODEL_VERSION,
        "model_type": "hybrid_policy_unfitted_reputation",
        "data_source": "razorpay_test_mode_only",
        "learned_calibrator_active": False,
        "operational_policy_active": True,
        "artifact_missing": not MODEL_PATH.exists(),
        "refit_allowed": refit_allowed,
        "readiness": readiness,
        "no_additional_payments_required": True,
        "safety_note": "Locked artifact missing; deterministic/Bayesian policy fallback remains active. Automatic refitting is disabled unless MERCHANTOS_ALLOW_MODEL_REFIT=true.",
    }


def _runtime_thresholds(manifest: dict[str, Any]) -> tuple[float, float]:
    """Return the validated review threshold and a separate critical-risk tier.

    v1.1 artifacts stored 0.85 as review_threshold even though the learned
    calibrator selected a lower validated threshold. v1.1.1 migrates those
    artifacts in memory without refitting them.
    """
    candidates = [
        (manifest.get("holdout") or {}).get("threshold"),
        (manifest.get("test") or {}).get("threshold"),
        (manifest.get("validation") or {}).get("threshold"),
        manifest.get("review_threshold"),
    ]
    review = next((float(v) for v in candidates if v is not None), 0.64)
    critical = float(manifest.get("critical_risk_threshold", CRITICAL_RISK_THRESHOLD))
    return review, critical


def score_components_for_event(event: PaymentEvent, events: list[PaymentEvent]) -> tuple[dict[str, float | None], dict[str, Any]]:
    """Return separate policy, calibrator, and final hybrid scores for observability."""
    status = ensure_production_model(events)
    if not MODEL_PATH.exists():
        policy = _policy_score(event, events, {})
        return {"policy_score": policy, "calibrator_probability": None, "final_score": policy}, status
    bundle = joblib.load(MODEL_PATH)
    reputation = bundle.get("reputation") or {}
    policy = _policy_score(event, events, reputation)
    calibrator = bundle.get("pipeline") if status.get("learned_calibrator_active") else None
    if calibrator is None:
        return {"policy_score": policy, "calibrator_probability": None, "final_score": policy}, status
    frame = temporal_behavior_features(events)
    row = frame[frame["event_id"] == event.event_id]
    if row.empty:
        return {"policy_score": policy, "calibrator_probability": None, "final_score": policy}, status
    cols = bundle["feature_columns"]
    prob = float(calibrator.predict_proba(row[cols])[:, 1][0])
    hybrid = round(min(max(policy, 0.65 * policy + 0.35 * prob), 0.99), 4)
    return {"policy_score": round(policy, 4), "calibrator_probability": round(prob, 4), "final_score": hybrid}, status


def model_status(events: list[PaymentEvent] | None = None) -> dict[str, Any]:
    if not MODEL_PATH.exists():
        if events is not None and dataset_readiness(events)["ready"]:
            return ensure_production_model(events)
        return {"trained": False, "active": True, "operational_policy_active": True, "model_version": MODEL_VERSION, "data_source": "razorpay_test_mode_only", "learned_calibrator_active": False}
    try:
        bundle = joblib.load(MODEL_PATH)
        manifest = dict(bundle.get("manifest") or {})
    except Exception as exc:
        return {"trained": False, "active": True, "operational_policy_active": True, "model_version": MODEL_VERSION, "error": str(exc), "learned_calibrator_active": False, "data_source": "razorpay_test_mode_only"}
    if manifest.get("data_source") != "razorpay_test_mode_only":
        return {"trained": True, "active": True, "operational_policy_active": True, "model_version": MODEL_VERSION, "learned_calibrator_active": False, "rejected": "non-Test-Mode artifact", "data_source": "razorpay_test_mode_only"}
    review_threshold, critical_risk_threshold = _runtime_thresholds(manifest)
    return {
        **manifest,
        "review_threshold": review_threshold,
        "threshold": review_threshold,
        "critical_risk_threshold": critical_risk_threshold,
        "threshold_policy": "validated_review_threshold_with_separate_critical_tier",
        "operational_policy_active": True,
    }


def _policy_score(event: PaymentEvent, events: list[PaymentEvent], reputation: dict[str, Any] | None = None) -> float:
    prior = [e for e in events if e.timestamp < event.timestamp or (e.timestamp == event.timestamp and e.event_id < event.event_id)]
    same_customer = [e for e in prior if e.customer_id == event.customer_id]
    same_order = [e for e in prior if e.order_id == event.order_id]
    known_inst = event.instrument_id not in {"", "unknown"}
    same_inst = [e for e in prior if known_inst and e.instrument_id == event.instrument_id]
    score = 0.04

    # Behavioral evidence available even in localhost experiments.
    if len(same_order) >= 1: score += min(0.18, 0.08 * len(same_order))
    recent10 = [e for e in same_customer if (event.timestamp - e.timestamp).total_seconds() <= 600]
    recent60 = [e for e in same_customer if (event.timestamp - e.timestamp).total_seconds() <= 3600]
    if len(recent10) >= 2: score += min(0.22, 0.06 * len(recent10))
    elif len(recent60) >= 3: score += min(0.15, 0.03 * len(recent60))
    if len(same_customer) >= 2:
        fail_rate = sum(e.event_type == "payment.failed" for e in same_customer) / len(same_customer)
        if fail_rate >= 0.75: score += 0.08

    if known_inst:
        inst_customers = len({e.customer_id for e in same_inst})
        if inst_customers >= 2: score += min(0.24, 0.07 * inst_customers)

    # Historical adjudication reputation learned only from earlier/finalized Test Mode labels.
    if reputation:
        c = (reputation.get("customers") or {}).get(event.customer_id)
        if c and c.get("total", 0) >= 2:
            posterior = float(c.get("posterior", 0.25))
            if posterior >= 0.65: score += 0.48
            elif posterior >= 0.50: score += 0.30
            elif posterior <= 0.15: score -= 0.05
        if known_inst:
            i = (reputation.get("instruments") or {}).get(event.instrument_id)
            if i and i.get("total", 0) >= 2 and float(i.get("posterior", 0.25)) >= 0.60:
                score += 0.20

    # Use device/IP only if the dataset proves those identifiers have diversity.
    q = identity_quality(events)
    if q["device_features_allowed"] and event.device_id not in {"", "unknown"}:
        dev_customers = len({e.customer_id for e in prior if e.device_id == event.device_id})
        if dev_customers >= 3: score += min(0.22, 0.04 * dev_customers)
    if q["ip_features_allowed"] and event.ip_address not in {"", "unknown", "0.0.0.0"}:
        ip_customers = len({e.customer_id for e in prior if e.ip_address == event.ip_address})
        if ip_customers >= 4: score += min(0.16, 0.025 * ip_customers)
    return round(max(0.01, min(score, 0.99)), 4)


def learned_score_for_event(event: PaymentEvent, events: list[PaymentEvent]) -> tuple[float | None, dict[str, Any]]:
    components, status = score_components_for_event(event, events)
    return float(components["final_score"]), status


def learned_scores_for_events(events: list[PaymentEvent]) -> tuple[dict[str, float], dict[str, Any]]:
    status = ensure_production_model(events)
    if not MODEL_PATH.exists():
        return ({e.event_id: _policy_score(e, events, {}) for e in events}, status)
    bundle = joblib.load(MODEL_PATH)
    reputation = bundle.get("reputation") or {}
    scores = {e.event_id: _policy_score(e, events, reputation) for e in events}
    calibrator = bundle.get("pipeline") if status.get("learned_calibrator_active") else None
    if calibrator is not None and events:
        frame = temporal_behavior_features(events)
        cols = bundle["feature_columns"]
        probs = calibrator.predict_proba(frame[cols])[:, 1]
        for event_id, prob in zip(frame["event_id"], probs):
            policy = scores.get(event_id, 0.04)
            scores[event_id] = round(min(max(policy, 0.65 * policy + 0.35 * float(prob)), 0.99), 4)
    return (scores, status)
