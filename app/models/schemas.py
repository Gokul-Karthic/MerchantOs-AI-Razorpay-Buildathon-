from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


TestScenarioLabel = Literal[
    "UNLABELED",
    "NORMAL",
    "CONTROLLED_ABUSE",
    "LEGIT_SHARED_NETWORK",
]


class PaymentEvent(BaseModel):
    event_id: str
    event_type: str
    order_id: str
    payment_id: str | None = None
    customer_id: str
    amount: float = Field(gt=0)
    currency: str = "INR"
    method: str = "unknown"
    bank: str = "unknown"
    device_id: str = "unknown"
    ip_address: str = "unknown"
    instrument_id: str = "unknown"
    merchant_id: str = "merchant-test"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "razorpay_test_mode"
    scenario_label: TestScenarioLabel = "UNLABELED"
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    event_id: str
    auto_execute_test_action: bool = False


class InterventionOption(BaseModel):
    action: Literal[
        "retry_same_method",
        "alternate_method",
        "payment_link",
        "wait",
        "escalate_review",
        "monitor",
    ]
    expected_recovery_probability: float = Field(ge=0, le=1)
    expected_recovery_inr: float = Field(ge=0)
    expected_cost_inr: float = Field(ge=0)
    risk_penalty_inr: float = Field(ge=0)
    expected_net_value_inr: float
    operational_risk: Literal["low", "medium", "high"]
    rationale: str


class DecisionResponse(BaseModel):
    event_id: str
    risk_score: float
    revenue_at_risk: float
    recommended_action: str
    confidence: float
    reason: str
    guardrail: str
    simulation: dict[str, float]
    audit_id: str
    incident_id: str | None = None
    guardrail_status: Literal[
        "OBSERVATION_ONLY", "SIMULATION_ONLY", "AUTO_ALLOWED_TEST", "APPROVAL_REQUIRED", "BLOCKED"
    ] = "SIMULATION_ONLY"
    approval_id: str | None = None
    action_id: str | None = None
    digital_twin: list[InterventionOption] = Field(default_factory=list)
    learned_risk_score: float | None = None
    deterministic_risk_score: float | None = None


class RiskCluster(BaseModel):
    cluster_id: str
    risk_score: float
    members: int
    estimated_exposure: float
    entities: dict[str, list[str]]
    evidence: list[str] = Field(default_factory=list)
    detector: str = "razorpay-testmode-graph-evidence"
    mean_model_score: float | None = None
    max_model_score: float | None = None
    model_flagged_event_ratio: float = 0.0
    high_risk_event_ratio: float = 0.0
    failure_rate: float = 0.0
    entity_concentration: float = 0.0
    strong_shared_entity_types: int = 0
    classification: Literal[
        "HIGH_RISK_RING", "SUSPICIOUS_CLUSTER", "MONITOR", "BENIGN_SHARED_NETWORK"
    ] = "MONITOR"
    risk_level: Literal["high", "medium", "low"] = "low"
    recommended_action: Literal["ESCALATE_REVIEW", "REVIEW", "MONITOR", "NO_ACTION"] = "MONITOR"
    action_allowed: bool = False
    validation_reasons: list[str] = Field(default_factory=list)


class RiskGraphScore(BaseModel):
    event_id: str
    risk_score: float
    review_threshold: float = 0.64
    critical_risk_threshold: float | None = 0.85
    flagged_for_review: bool
    feature_evidence: list[str] = Field(default_factory=list)
    scoring_mode: str = "deterministic_graph_evidence"
    active_ml_model: bool = False
    action_allowed: bool = False
    deterministic_risk_score: float | None = None
    learned_risk_score: float | None = None
    model_version: str | None = None


class PayGuardIncident(BaseModel):
    incident_id: str
    status: Literal["OPEN", "MONITOR", "RESOLVED"] = "OPEN"
    severity: Literal["low", "medium", "high", "critical"]
    scope: str
    method: str
    bank: str
    recent_transactions: int
    recent_failures: int
    recent_failure_rate: float
    baseline_failure_rate: float
    degradation: float
    revenue_at_risk: float
    root_cause: str
    evidence: list[str] = Field(default_factory=list)
    window_start: datetime
    window_end: datetime


class RazorpayOrderCreateRequest(BaseModel):
    amount_inr: float = Field(gt=0, le=1_000_000)
    receipt: str | None = Field(default=None, max_length=40)
    customer_ref: str | None = Field(default=None, max_length=120)
    scenario_label: TestScenarioLabel = "UNLABELED"
    session_id: str | None = Field(default=None, max_length=160)
    device_id: str | None = Field(default=None, max_length=160)
    notes: dict[str, str] = Field(default_factory=dict)


class PaymentJourneyCreateRequest(BaseModel):
    """Create a genuine Razorpay Test Mode payment journey.

    Journey payments are intentionally UNLABELED: experiment labels are never
    used in the live demo / operational trace workflow.
    """

    amount_inr: float = Field(gt=0, le=1_000_000)
    customer_ref: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=240)


class JourneyAnalyzeRequest(BaseModel):
    auto_execute_test_action: bool = False
    force_redecide: bool = False


class RazorpaySyncRequest(BaseModel):
    count: int = Field(default=100, ge=1, le=100)
    skip: int = Field(default=0, ge=0)


class ApprovalDecisionRequest(BaseModel):
    approved: bool
    note: str | None = Field(default=None, max_length=500)
    execute_if_approved: bool = True


class OrchestratorRunRequest(BaseModel):
    limit: int = Field(default=25, ge=1, le=200)
    auto_execute_test_actions: bool = False
    force_redecide: bool = False


class RiskModelTrainRequest(BaseModel):
    activate: bool = True
