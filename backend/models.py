from pydantic import BaseModel, Field
from typing import Any, Optional
from enum import Enum


# ── Enums ─────────────────────────────────────────────────────────────────────

class SourceType(str, Enum):
    csv_json     = "csv_json"
    pdf_report   = "pdf_report"
    news_article = "news_article"
    dashboard    = "dashboard"
    realtime_feed = "realtime_feed"
    text         = "text"


class ContentType(str, Enum):   # kept for backward-compat
    text     = "text"
    pdf_text = "pdf_text"
    news     = "news"


# ── Request ───────────────────────────────────────────────────────────────────

class ContentSource(BaseModel):
    source_id: str
    source_type: SourceType
    content: str
    url: Optional[str] = None
    timestamp_utc: Optional[str] = None    # ISO 8601
    credibility_score: Optional[float] = None  # 0.0–1.0 caller hint


class AnalyzeRequest(BaseModel):
    sources: Optional[list[ContentSource]] = None  # preferred: multi-source
    content: Optional[str] = None                  # fallback: single text blob
    content_type: ContentType = ContentType.text
    session_id: Optional[str] = None


# ── Parser Agent ──────────────────────────────────────────────────────────────

class DisruptionEntity(BaseModel):
    disruption_type: str   # e.g. "port_strike"
    location: str          # e.g. "Port of Karachi"
    affected_region: str   # e.g. "Lahore Distribution Center"
    duration_days: int
    severity: str          # "low" | "medium" | "high" | "critical"
    raw_facts: list[str]


class TemporalSignal(BaseModel):
    metric: str
    trend: str             # "rising" | "falling" | "stable" | "spike"
    change_pct: float
    observation: str


class ContradictionRecord(BaseModel):
    metric: str
    source_a_id: str
    source_a_claim: str
    source_b_id: str
    source_b_claim: str
    resolution: str        # "source_a_preferred" | "source_b_preferred" | "unresolved"
    resolution_reason: str


class ParsedContent(BaseModel):
    entities: list[DisruptionEntity]
    key_metrics: dict[str, Any]
    time_horizon: str
    sources_parsed: int = 1
    noise_filtered: int = 0
    credibility_scores: dict[str, float] = {}   # source_id → 0.0–1.0
    temporal_signals: list[TemporalSignal] = []
    contradictions: list[ContradictionRecord] = []


# ── Insight Agent ─────────────────────────────────────────────────────────────

class CausalChain(BaseModel):
    cause: str
    immediate_effect: str
    downstream_effect: str
    financial_impact_usd: float
    probability_pct: int


class Insight(BaseModel):
    title: str
    causal_chains: list[CausalChain]
    total_exposure_usd: float
    urgency: str                  # "immediate" | "24h" | "48h" | "week"
    affected_skus: list[str]
    key_risks: list[str] = []
    contradiction_resolutions: list[str] = []


# ── Planner Agent ─────────────────────────────────────────────────────────────

class ActionType(str, Enum):
    reroute           = "reroute_shipment"
    update_pricing    = "update_pricing"
    send_notification = "send_notification"
    activate_stock    = "activate_safety_stock"
    update_inventory  = "update_inventory"


class ActionConstraint(BaseModel):
    budget_usd: float
    deadline_hours: int
    max_retries: int = 2
    rollback_on_failure: bool = True


class RecommendedAction(BaseModel):
    action_id: str
    action_type: ActionType
    title: str
    description: str
    confidence_pct: int
    estimated_savings_usd: float
    parameters: dict[str, Any]
    constraints: Optional[ActionConstraint] = None
    feasibility_status: str = "feasible"   # "feasible" | "infeasible" | "modified"
    feasibility_note: Optional[str] = None
    depends_on: list[str] = []             # action_ids that must succeed first


class ActionPlan(BaseModel):
    ranked_actions: list[RecommendedAction]
    primary_action_id: str
    rationale: str
    total_budget_usd: float = 0.0
    constraint_violations: list[str] = []


# ── Executor Agent ────────────────────────────────────────────────────────────

class ExecutionStep(BaseModel):
    step: int
    action: str
    endpoint: str
    request_payload: dict[str, Any]
    response_payload: dict[str, Any]
    latency_ms: int
    success: bool
    error: Optional[str] = None


class StateSnapshot(BaseModel):
    inventory: dict[str, Any]
    routes: dict[str, Any]
    pricing: dict[str, Any]
    notifications_count: int
    penalty_exposure_usd: float = 0.0


class ChainStepResult(BaseModel):
    action_id: str
    action_type: str
    action_title: str
    status: str        # "success" | "failed" | "retried_ok" | "rolled_back" | "skipped"
    attempt: int
    api_steps: list[ExecutionStep]
    state_before: StateSnapshot
    state_after: StateSnapshot
    error: Optional[str] = None
    recovery_note: Optional[str] = None
    latency_ms: int


class ExecutionResult(BaseModel):
    chain_steps: list[ChainStepResult]
    before_state: StateSnapshot
    after_state: StateSnapshot
    total_actions_attempted: int
    total_actions_succeeded: int
    total_actions_failed: int
    outcome_summary: str
    penalty_reduction_usd: float
    eta_improvement_days: float
    total_latency_ms: int
    # backward-compat flat fields
    action_id: str = ""
    action_type: str = ""
    steps: list[ExecutionStep] = []


# ── Pipeline Response ─────────────────────────────────────────────────────────

class AgentStep(BaseModel):
    agent: str
    status: str                   # "running" | "done" | "error"
    output: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class AnalyzeResponse(BaseModel):
    session_id: str
    parsed: ParsedContent
    insight: Insight
    plan: ActionPlan
    execution: Optional[ExecutionResult] = None
    agent_trace: list[AgentStep]
