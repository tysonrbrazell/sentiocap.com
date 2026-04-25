"""
Pydantic v2 schemas for all SentioCap API request/response bodies.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Enums (mirroring DB enums)
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class PlanType(str, Enum):
    annual_budget = "annual_budget"
    reforecast = "reforecast"
    scenario = "scenario"


class PlanStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    locked = "locked"


class L1Type(str, Enum):
    RTB = "RTB"
    CTB = "CTB"


class L2Category(str, Enum):
    RTB_OPS = "RTB-OPS"
    RTB_MNT = "RTB-MNT"
    RTB_CMP = "RTB-CMP"
    RTB_SUP = "RTB-SUP"
    CTB_GRW = "CTB-GRW"
    CTB_TRN = "CTB-TRN"
    CTB_EFF = "CTB-EFF"
    CTB_INN = "CTB-INN"


class L3Domain(str, Enum):
    TECH = "TECH"
    PPL = "PPL"
    COM = "COM"
    PRD = "PRD"
    FAC = "FAC"
    FIN = "FIN"
    CRP = "CRP"
    DAT = "DAT"


class ClassificationMethod(str, Enum):
    ai_auto = "ai_auto"
    user_manual = "user_manual"
    rule_based = "rule_based"


class InvestmentStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class BenefitCalcMethod(str, Enum):
    formula = "formula"
    milestone = "milestone"
    proxy = "proxy"


class ConfidenceLevel(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"


class VarianceSignal(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    org_name: str
    sector: str
    email: EmailStr
    name: str
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: UserRole
    org_id: UUID

    model_config = {"from_attributes": True}


class OrgResponse(BaseModel):
    id: UUID
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    ticker: Optional[str] = None
    revenue: Optional[float] = None
    employees: Optional[int] = None
    fiscal_year_end: Optional[str] = None
    currency: str = "USD"

    model_config = {"from_attributes": True}


class UserWithOrgResponse(UserResponse):
    org: Optional[OrgResponse] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class RegisterResponse(TokenResponse):
    org: OrgResponse


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

class OrgCreate(BaseModel):
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    ticker: Optional[str] = None
    revenue: Optional[float] = None
    employees: Optional[int] = None
    fiscal_year_end: Optional[str] = None
    currency: str = "USD"


class OrgUpdate(BaseModel):
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    ticker: Optional[str] = None
    revenue: Optional[float] = None
    employees: Optional[int] = None
    fiscal_year_end: Optional[str] = None


# ---------------------------------------------------------------------------
# Plans
# ---------------------------------------------------------------------------

class PlanCreate(BaseModel):
    name: str
    plan_type: PlanType = PlanType.annual_budget
    fiscal_year: int
    notes: Optional[str] = None


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[PlanStatus] = None


class PlanSummaryStats(BaseModel):
    rtb_total: float = 0
    ctb_total: float = 0
    rtb_pct: float = 0
    ctb_pct: float = 0
    by_l2: dict[str, float] = {}


class PlanListItem(BaseModel):
    id: UUID
    name: str
    plan_type: PlanType
    fiscal_year: int
    status: PlanStatus
    total_budget: Optional[float] = None
    line_item_count: int = 0
    classified_count: int = 0
    confirmed_count: int = 0
    created_at: datetime
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PlanListResponse(BaseModel):
    plans: list[PlanListItem]
    total: int


class PlanResponse(BaseModel):
    id: UUID
    name: str
    plan_type: PlanType
    fiscal_year: int
    status: PlanStatus
    total_budget: Optional[float] = None
    currency: str = "USD"
    approved_by: Optional[dict] = None
    approved_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    summary: Optional[PlanSummaryStats] = None
    line_items: list["PlanLineItemResponse"] = []
    line_items_total: int = 0
    line_items_page: int = 1
    line_items_per_page: int = 50

    model_config = {"from_attributes": True}


class PlanLineItemResponse(BaseModel):
    id: UUID
    plan_id: UUID
    source_description: str
    source_cost_center: Optional[str] = None
    source_gl_account: Optional[str] = None
    source_row_number: Optional[int] = None
    classified_l1: Optional[L1Type] = None
    classified_l2: Optional[L2Category] = None
    classified_l3: Optional[L3Domain] = None
    classified_l4: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_method: ClassificationMethod = ClassificationMethod.ai_auto
    user_confirmed: bool = False
    jan: float = 0
    feb: float = 0
    mar: float = 0
    apr: float = 0
    may: float = 0
    jun: float = 0
    jul: float = 0
    aug: float = 0
    sep: float = 0
    oct: float = 0
    nov: float = 0
    dec: float = 0
    annual_total: float = 0
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class LineItemUpdate(BaseModel):
    classified_l1: Optional[L1Type] = None
    classified_l2: Optional[L2Category] = None
    classified_l3: Optional[L3Domain] = None
    classified_l4: Optional[str] = None
    user_confirmed: Optional[bool] = None
    notes: Optional[str] = None


class PlanApproveRequest(BaseModel):
    notes: Optional[str] = None


class PlanApproveResponse(BaseModel):
    id: UUID
    status: PlanStatus
    approved_by: Optional[dict] = None
    approved_at: Optional[datetime] = None


class ClassifyPlanRequest(BaseModel):
    mode: str = "unclassified_only"  # unclassified_only | all | low_confidence
    confidence_threshold: float = 0.7


class ClassifyPlanResponse(BaseModel):
    job_id: str
    status: str
    total_items: int
    message: str


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class UploadPreviewRow(BaseModel):
    row: int
    source_description: str
    source_cost_center: Optional[str] = None
    source_gl_account: Optional[str] = None
    amounts: dict[str, float] = {}
    annual_total: float = 0
    suggested_classification: Optional["ClassificationResult"] = None


class UploadPreviewResponse(BaseModel):
    upload_id: str
    rows_detected: int
    columns_detected: list[str]
    preview: list[UploadPreviewRow]
    preview_count: int


# ---------------------------------------------------------------------------
# Actuals
# ---------------------------------------------------------------------------

class ActualsUploadResponse(BaseModel):
    period: str
    rows_imported: int
    rows_classified: int
    rows_flagged: int
    total_amount: float
    variances_updated: bool


class ActualsResponse(BaseModel):
    period: str
    total_amount: float
    by_l2: dict[str, float] = {}
    line_items: list[dict] = []


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class ClassificationRequest(BaseModel):
    description: str
    cost_center: Optional[str] = None
    gl_account: Optional[str] = None
    amount: Optional[float] = None
    context: Optional[dict] = None


class ClassificationAlternative(BaseModel):
    l2: str
    l3: str
    l4: str
    confidence: float
    reason: str


class ClassificationResult(BaseModel):
    classified_l1: L1Type
    classified_l2: str
    classified_l3: str
    classified_l4: str
    confidence: float
    method: str = "ai_auto"
    reasoning: Optional[str] = None
    alternatives: list[ClassificationAlternative] = []


class BatchClassificationItem(BaseModel):
    id: str
    description: str
    cost_center: Optional[str] = None
    gl_account: Optional[str] = None
    amount: Optional[float] = None


class BatchClassificationRequest(BaseModel):
    items: list[BatchClassificationItem]
    context: Optional[dict] = None


class BatchClassificationResultItem(BaseModel):
    id: str
    classified_l1: L1Type
    classified_l2: str
    classified_l3: str
    classified_l4: str
    confidence: float
    method: str = "ai_auto"
    reasoning: Optional[str] = None


class BatchClassificationResponse(BaseModel):
    results: list[BatchClassificationResultItem]
    total: int
    auto_confirmed: int
    needs_review: int
    flagged: int


# ---------------------------------------------------------------------------
# Investments
# ---------------------------------------------------------------------------

class BenefitCreate(BaseModel):
    benefit_type: str
    description: str
    calculation_method: BenefitCalcMethod = BenefitCalcMethod.formula
    formula: Optional[str] = None
    target_value: Optional[float] = None
    actual_value: Optional[float] = None
    measurement_start: Optional[date] = None
    measurement_source: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.medium
    notes: Optional[str] = None


class BenefitResponse(BenefitCreate):
    id: UUID
    investment_id: UUID
    realization_pct: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    l2_category: Optional[L2Category] = None
    l3_domain: Optional[L3Domain] = None
    l4_activity: Optional[str] = None
    status: InvestmentStatus = InvestmentStatus.proposed
    start_date: Optional[date] = None
    target_completion: Optional[date] = None
    planned_total: Optional[float] = None
    strategic_rating: Optional[int] = Field(None, ge=1, le=5)
    plan_id: Optional[UUID] = None
    benefits: list[BenefitCreate] = []
    notes: Optional[str] = None


class InvestmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None
    l2_category: Optional[L2Category] = None
    l3_domain: Optional[L3Domain] = None
    l4_activity: Optional[str] = None
    status: Optional[InvestmentStatus] = None
    start_date: Optional[date] = None
    target_completion: Optional[date] = None
    planned_total: Optional[float] = None
    actual_total: Optional[float] = None
    strategic_rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None


class ROIMetrics(BaseModel):
    planned_roi: Optional[float] = None
    current_roi: Optional[float] = None
    payback_months: Optional[int] = None
    npv_roi: Optional[float] = None
    composite_score: Optional[int] = None
    signal: VarianceSignal = VarianceSignal.YELLOW


class InvestmentROIResponse(BaseModel):
    investment_id: UUID
    name: str
    total_costs: float
    total_benefits: float
    roi: Optional[float] = None
    roi_pct: Optional[float] = None
    npv_roi: Optional[float] = None
    payback_months: Optional[int] = None
    discount_rate: float = 0.10
    composite_score: Optional[int] = None
    signal: VarianceSignal = VarianceSignal.YELLOW
    benefit_breakdown: list[dict] = []
    spend_vs_plan: dict = {}


class InvestmentResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    l2_category: Optional[str] = None
    l3_domain: Optional[str] = None
    l4_activity: Optional[str] = None
    status: InvestmentStatus
    start_date: Optional[date] = None
    target_completion: Optional[date] = None
    planned_total: Optional[float] = None
    actual_total: float = 0
    strategic_rating: Optional[int] = None
    benefits: list[BenefitResponse] = []
    spend_monthly: list[dict] = []
    roi: Optional[ROIMetrics] = None
    benefit_count: int = 0
    benefits_realized_pct: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    total_planned: float = 0
    total_actual: float = 0
    deployment_rate: float = 0
    portfolio_roi: Optional[float] = None
    at_risk_count: int = 0


class InvestmentListResponse(BaseModel):
    investments: list[InvestmentResponse]
    total: int
    portfolio_summary: PortfolioSummary


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class L2Summary(BaseModel):
    amount: float
    pct: float
    signal: VarianceSignal


class RTBSummary(BaseModel):
    total: float
    pct: float
    peer_median_pct: Optional[float] = None
    signal: VarianceSignal
    vs_plan_pct: Optional[float] = None


class CTBSummary(BaseModel):
    total: float
    pct: float
    peer_median_pct: Optional[float] = None
    signal: VarianceSignal
    deployment_rate: Optional[float] = None


class InvestmentSummary(BaseModel):
    active_count: int = 0
    at_risk_count: int = 0
    portfolio_roi: Optional[float] = None
    deployment_rate: Optional[float] = None


class DashboardSummary(BaseModel):
    org: dict
    fiscal_year: int
    plan_id: Optional[UUID] = None
    plan_name: Optional[str] = None
    total_budget: float = 0
    rtb: RTBSummary
    ctb: CTBSummary
    investments: InvestmentSummary
    by_l2: dict[str, L2Summary] = {}


class TreemapNode(BaseModel):
    name: str
    value: float
    color: Optional[str] = None
    pct: Optional[float] = None
    children: list["TreemapNode"] = []


class VarianceRecord(BaseModel):
    l2_category: str
    planned: float
    actual: float
    variance_amount: float
    variance_pct: float
    ytd_planned: float = 0
    ytd_actual: float = 0
    full_year_forecast: Optional[float] = None
    signal: VarianceSignal
    signal_reason: Optional[str] = None


class VarianceResponse(BaseModel):
    period: str
    plan_id: Optional[UUID] = None
    variances: list[VarianceRecord]


class BenchmarkComparisonItem(BaseModel):
    l2_category: str
    org_pct: Optional[float] = None
    peer_p25: Optional[float] = None
    peer_median: Optional[float] = None
    peer_p75: Optional[float] = None
    signal: VarianceSignal
    insight: Optional[str] = None


class BenchmarkResponse(BaseModel):
    org: dict
    benchmark_year: int
    benchmark_sector: str
    comparison: list[BenchmarkComparisonItem]


class TimeseriesPoint(BaseModel):
    period: str
    rtb_actual: Optional[float] = None
    ctb_actual: Optional[float] = None
    rtb_planned: Optional[float] = None
    ctb_planned: Optional[float] = None
    rtb_pct: Optional[float] = None
    ctb_pct: Optional[float] = None


class TimeseriesResponse(BaseModel):
    series: list[TimeseriesPoint]


# ---------------------------------------------------------------------------
# Sector Benchmarks
# ---------------------------------------------------------------------------

class SectorBenchmarkItem(BaseModel):
    l2_category: str
    median_pct: Optional[float] = None
    p25_pct: Optional[float] = None
    p75_pct: Optional[float] = None
    mean_pct: Optional[float] = None
    n_companies: Optional[int] = None


class SectorBenchmarksResponse(BaseModel):
    sector: str
    year: int
    n_companies: Optional[int] = None
    benchmarks: list[SectorBenchmarkItem]


class PeerData(BaseModel):
    ticker: str
    company: Optional[str] = None
    revenue: Optional[float] = None
    ctb_pct_rev: Optional[float] = None
    rd: Optional[float] = None
    capex: Optional[float] = None
    sw_capitalized: Optional[float] = None
    return_1yr: Optional[float] = None
    return_3yr: Optional[float] = None


class PeerComparisonResponse(BaseModel):
    year: int
    peers: list[PeerData]
    correlation: Optional[dict] = None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | running | completed | failed
    progress: int = 0
    total_items: int = 0
    processed_items: int = 0
    errors: int = 0
    result_summary: Optional[dict] = None
    completed_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------

class DecisionSeverity(str, Enum):
    critical = "critical"
    warning = "warning"
    info = "info"


class DecisionStatus(str, Enum):
    new = "new"
    acknowledged = "acknowledged"
    in_progress = "in_progress"
    resolved = "resolved"
    dismissed = "dismissed"


class DecisionResponse(BaseModel):
    id: UUID
    org_id: UUID
    investment_id: Optional[UUID] = None
    plan_id: Optional[UUID] = None
    category: str
    category_number: int
    severity: DecisionSeverity
    trigger_type: Optional[str] = None
    trigger_data: dict = {}
    title: str
    description: str
    recommended_action: str
    impact_estimate: Optional[str] = None
    owner: Optional[str] = None
    status: DecisionStatus
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[UUID] = None
    resolution_notes: Optional[str] = None
    investment_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DecisionUpdate(BaseModel):
    status: Optional[str] = None
    owner: Optional[str] = None
    resolution_notes: Optional[str] = None


class DecisionSummary(BaseModel):
    total: int = 0
    active: int = 0
    by_severity: dict[str, int] = {}
    by_status: dict[str, int] = {}


class DecisionScanResult(BaseModel):
    new_decisions: int
    decision_ids: list[str] = []


# ---------------------------------------------------------------------------
# Memory — Agent Learning Layer
# ---------------------------------------------------------------------------

class GlossaryEntryUpdate(BaseModel):
    """Partial update for a firm_glossary entry."""
    firm_term: Optional[str] = None
    mapped_l1: Optional[str] = None
    mapped_l2: Optional[str] = None
    mapped_l3: Optional[str] = None
    mapped_l4: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    notes: Optional[str] = None


class GlossaryEntry(BaseModel):
    id: UUID
    org_id: UUID
    firm_term: str
    mapped_l1: Optional[str] = None
    mapped_l2: Optional[str] = None
    mapped_l3: Optional[str] = None
    mapped_l4: Optional[str] = None
    confidence: float = 1.0
    source: str = "manual"  # 'manual', 'learned', 'correction'
    usage_count: int = 1
    last_used_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SignalPreferenceUpdate(BaseModel):
    """Manually override sensitivity for a signal category."""
    sensitivity_override: Optional[float] = Field(
        None,
        description="null=auto, 0=suppress, 0.5=less, 1.0=normal, 2.0=amplify",
    )
    notes: Optional[str] = None


class SignalPreference(BaseModel):
    id: UUID
    org_id: UUID
    category: str
    action: str  # 'acknowledged', 'resolved', 'dismissed'
    count: int = 1
    last_action_at: Optional[datetime] = None
    sensitivity_override: Optional[float] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PeerGroupCreate(BaseModel):
    name: str
    tickers: list[str] = Field(..., min_length=1, description="List of peer company tickers")
    is_default: bool = False


class PeerGroup(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    tickers: list[str]
    is_default: bool = False
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ForecastAccuracy(BaseModel):
    id: UUID
    org_id: UUID
    period: str  # 'YYYY-MM'
    forecast_date: date
    l2_category: str
    forecasted_amount: float
    actual_amount: Optional[float] = None
    variance_pct: Optional[float] = None
    bias_direction: Optional[str] = None  # 'over' or 'under'
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DecisionOutcome(BaseModel):
    id: UUID
    org_id: UUID
    decision_id: Optional[UUID] = None
    category: str
    action_taken: str  # 'killed', 'accelerated', 'reallocated', 'extended', 'ignored'
    investment_id: Optional[UUID] = None
    metrics_before: dict = {}
    metrics_after: dict = {}
    outcome_score: Optional[float] = None  # -1 to 1
    outcome_notes: Optional[str] = None
    measured_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReportFeedbackCreate(BaseModel):
    report_type: str = Field(
        ...,
        description="e.g. 'board_deck', 'monthly_briefing', 'investment_case'",
    )
    score: float = Field(..., ge=1, le=5, description="1=poor, 5=excellent")
    feedback_text: Optional[str] = None


class ReportFeedback(BaseModel):
    id: UUID
    org_id: UUID
    report_type: str
    preferences: dict = {}
    feedback_scores: list[dict] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NetworkIntelligence(BaseModel):
    id: UUID
    intelligence_type: str
    key: str
    data: dict
    n_companies: int = 0
    confidence: float = 0.5
    last_updated: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# Update forward refs
PlanResponse.model_rebuild()
TreemapNode.model_rebuild()
UploadPreviewRow.model_rebuild()


# ---------------------------------------------------------------------------
# Connectors
# ---------------------------------------------------------------------------

class ConnectorTypeEnum(str, Enum):
    salesforce = "salesforce"
    jira = "jira"
    hubspot = "hubspot"
    dynamics = "dynamics"
    workday = "workday"
    sap = "sap"
    servicenow = "servicenow"


class ConnectorStatusEnum(str, Enum):
    disconnected = "disconnected"
    connected = "connected"
    syncing = "syncing"
    error = "error"


class SyncStatusEnum(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class ConnectorConfigResponse(BaseModel):
    id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    connector_type: str
    status: str = "disconnected"
    sync_frequency: str = "daily"
    last_sync_at: Optional[datetime] = None
    config: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_sync: Optional[dict] = None

    model_config = {"from_attributes": True}


class ConnectorSyncResponse(BaseModel):
    id: UUID
    connector_id: UUID
    org_id: UUID
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    records_synced: int = 0
    records_mapped: int = 0
    errors: list[dict] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ConnectorMappingResponse(BaseModel):
    id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    connector_type: str
    source_type: str
    source_id: str
    source_name: str
    investment_id: Optional[UUID] = None
    l2_category: Optional[str] = None
    mapping_method: str = "ai"
    confidence: float = 0.5
    confirmed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CrmRevenueDataResponse(BaseModel):
    id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    connector_type: str
    period: str
    source_product: Optional[str] = None
    source_segment: Optional[str] = None
    investment_id: Optional[UUID] = None
    pipeline_amount: float = 0
    closed_won_amount: float = 0
    new_logos: int = 0
    churned_amount: float = 0
    avg_deal_size: Optional[float] = None
    win_rate: Optional[float] = None
    avg_cycle_days: Optional[int] = None
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class EffortDataResponse(BaseModel):
    id: Optional[UUID] = None
    org_id: Optional[UUID] = None
    connector_type: str
    period: str
    source_project: Optional[str] = None
    source_epic: Optional[str] = None
    investment_id: Optional[UUID] = None
    hours_logged: float = 0
    effort_cost: float = 0
    story_points_completed: int = 0
    issues_total: int = 0
    issues_bugs: int = 0
    issues_features: int = 0
    issues_tasks: int = 0
    velocity_trend: Optional[float] = None
    backlog_growth: int = 0
    completion_pct: float = 0
    synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UnifiedCostView(BaseModel):
    investment_id: str
    investment_name: str
    l2_category: Optional[str] = None
    status: Optional[str] = None
    planned_cost: float = 0
    gl_actual_cost: float = 0
    effort_cost: float = 0
    effort_hours: float = 0
    revenue_pipeline: float = 0
    revenue_closed: float = 0
    new_logos: int = 0
    churn_amount: float = 0
    deployment_rate: Optional[float] = None
    effort_efficiency: Optional[float] = None
    roi_on_plan: Optional[float] = None
    roi_on_effort: Optional[float] = None
    pipeline_coverage: Optional[float] = None
    discrepancies: list[str] = []
    health_signals: list[dict] = []
    signal: str = "GREEN"  # GREEN | YELLOW | RED

    model_config = {"from_attributes": True}


class SyncResult(BaseModel):
    connector_type: str
    org_id: str
    status: str
    records_synced: int = 0
    records_mapped: int = 0
    errors: list[dict] = []
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ConnectorConnectRequest(BaseModel):
    auth_code: Optional[str] = None
    mock: bool = True  # default to mock mode


class MappingUpdateRequest(BaseModel):
    investment_id: Optional[UUID] = None
    l2_category: Optional[str] = None
    confirmed: Optional[bool] = None


# ---------------------------------------------------------------------------
# Fuzzy Matching
# ---------------------------------------------------------------------------

class MatchCandidateSchema(BaseModel):
    target_id: str
    target_name: str
    target_type: str  # 'investment' | 'rtb_category'
    confidence: float
    match_method: str
    reasoning: str
    allocation_pct: float = 100.0

    model_config = {"from_attributes": True}


class MatchResultSchema(BaseModel):
    source_id: str
    source_name: str
    source_type: str  # 'product' | 'project' | 'epic' | 'cost_center'
    source_system: str  # 'salesforce' | 'jira' | 'erp'
    match_status: str  # 'auto_matched' | 'needs_review' | 'unmatched'
    needs_review: bool
    best_match: Optional[MatchCandidateSchema] = None
    candidates: list[MatchCandidateSchema] = []

    model_config = {"from_attributes": True}


class MatchConfirmationRequest(BaseModel):
    source_id: str
    source_system: str
    source_name: str = ""
    target_id: str
    target_name: str = ""
    target_type: str = "investment"  # 'investment' | 'rtb_category'
    allocation_pct: float = 100.0


class MatchSplitRequest(BaseModel):
    source_id: str
    source_name: str
    source_system: str
    splits: list[dict]  # [{target_id, target_name, target_type, allocation_pct}]


class MatchStats(BaseModel):
    total: int = 0
    confirmed: int = 0
    auto_matched: int = 0
    needs_review: int = 0
    unmatched: int = 0
    quality_score: float = 0.0
    by_system: dict = {}

    model_config = {"from_attributes": True}
