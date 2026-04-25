// TypeScript types matching the API Pydantic schemas

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type UserRole = 'admin' | 'analyst' | 'viewer'

export type PlanType = 'annual_budget' | 'reforecast' | 'scenario'

export type PlanStatus = 'draft' | 'submitted' | 'approved' | 'locked'

export type L1Type = 'RTB' | 'CTB'

export type L2Category =
  | 'RTB-OPS'
  | 'RTB-MNT'
  | 'RTB-CMP'
  | 'RTB-SUP'
  | 'CTB-GRW'
  | 'CTB-TRN'
  | 'CTB-EFF'
  | 'CTB-INN'

export type L3Domain = 'TECH' | 'PPL' | 'COM' | 'PRD' | 'FAC' | 'FIN' | 'CRP' | 'DAT'

export type ClassificationMethod = 'ai_auto' | 'user_manual' | 'rule_based'

export type InvestmentStatus =
  | 'proposed'
  | 'approved'
  | 'in_progress'
  | 'completed'
  | 'cancelled'

export type BenefitCalcMethod = 'formula' | 'milestone' | 'proxy'

export type ConfidenceLevel = 'high' | 'medium' | 'low'

export type VarianceSignal = 'GREEN' | 'YELLOW' | 'RED'

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  org_name: string
  sector: string
  email: string
  name: string
  password: string
}

export interface UserResponse {
  id: string
  email: string
  name: string
  role: UserRole
  org_id: string
}

export interface OrgResponse {
  id: string
  name: string
  sector?: string
  industry?: string
  ticker?: string
  revenue?: number
  employees?: number
  fiscal_year_end?: string
  currency: string
}

export interface UserWithOrgResponse extends UserResponse {
  org?: OrgResponse
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: UserResponse
}

export interface RegisterResponse extends TokenResponse {
  org: OrgResponse
}

// ---------------------------------------------------------------------------
// Organizations
// ---------------------------------------------------------------------------

export interface OrgUpdate {
  name?: string
  sector?: string
  industry?: string
  ticker?: string
  revenue?: number
  employees?: number
  fiscal_year_end?: string
}

// ---------------------------------------------------------------------------
// Plans
// ---------------------------------------------------------------------------

export interface PlanCreate {
  name: string
  plan_type: PlanType
  fiscal_year: number
  notes?: string
}

export interface PlanSummaryStats {
  rtb_total: number
  ctb_total: number
  rtb_pct: number
  ctb_pct: number
  by_l2: Record<string, number>
}

export interface PlanListItem {
  id: string
  name: string
  plan_type: PlanType
  fiscal_year: number
  status: PlanStatus
  total_budget?: number
  line_item_count: number
  classified_count: number
  confirmed_count: number
  created_at: string
  approved_at?: string
}

export interface PlanListResponse {
  plans: PlanListItem[]
  total: number
}

export interface PlanLineItemResponse {
  id: string
  plan_id: string
  source_description: string
  source_cost_center?: string
  source_gl_account?: string
  source_row_number?: number
  classified_l1?: L1Type
  classified_l2?: L2Category
  classified_l3?: L3Domain
  classified_l4?: string
  classification_confidence?: number
  classification_method: ClassificationMethod
  user_confirmed: boolean
  jan: number
  feb: number
  mar: number
  apr: number
  may: number
  jun: number
  jul: number
  aug: number
  sep: number
  oct: number
  nov: number
  dec: number
  annual_total: number
  notes?: string
}

export interface PlanResponse {
  id: string
  name: string
  plan_type: PlanType
  fiscal_year: number
  status: PlanStatus
  total_budget?: number
  currency: string
  approved_by?: Record<string, unknown>
  approved_at?: string
  notes?: string
  created_at: string
  summary?: PlanSummaryStats
  line_items: PlanLineItemResponse[]
  line_items_total: number
  line_items_page: number
  line_items_per_page: number
}

export interface LineItemUpdate {
  classified_l1?: L1Type
  classified_l2?: L2Category
  classified_l3?: L3Domain
  classified_l4?: string
  user_confirmed?: boolean
  notes?: string
}

export interface ClassifyPlanResponse {
  job_id: string
  status: string
  total_items: number
  message: string
}

// ---------------------------------------------------------------------------
// Classification
// ---------------------------------------------------------------------------

export interface ClassificationResult {
  classified_l1: L1Type
  classified_l2: string
  classified_l3: string
  classified_l4: string
  confidence: number
  method: string
  reasoning?: string
  alternatives: Array<{
    l2: string
    l3: string
    l4: string
    confidence: number
    reason: string
  }>
}

export interface JobStatus {
  job_id: string
  status: 'queued' | 'running' | 'completed' | 'failed'
  progress: number
  total_items: number
  processed_items: number
  errors: number
  result_summary?: Record<string, unknown>
  completed_at?: string
}

// ---------------------------------------------------------------------------
// Investments
// ---------------------------------------------------------------------------

export interface BenefitCreate {
  benefit_type: string
  description: string
  calculation_method: BenefitCalcMethod
  formula?: string
  target_value?: number
  actual_value?: number
  measurement_start?: string
  measurement_source?: string
  confidence: ConfidenceLevel
  notes?: string
}

export interface BenefitResponse extends BenefitCreate {
  id: string
  investment_id: string
  realization_pct?: number
  created_at: string
}

export interface InvestmentCreate {
  name: string
  description?: string
  owner?: string
  l2_category?: L2Category
  l3_domain?: L3Domain
  l4_activity?: string
  status: InvestmentStatus
  start_date?: string
  target_completion?: string
  planned_total?: number
  strategic_rating?: number
  plan_id?: string
  benefits: BenefitCreate[]
  notes?: string
}

export interface ROIMetrics {
  planned_roi?: number
  current_roi?: number
  payback_months?: number
  npv_roi?: number
  composite_score?: number
  signal: VarianceSignal
}

export interface InvestmentResponse {
  id: string
  name: string
  description?: string
  owner?: string
  l2_category?: string
  l3_domain?: string
  l4_activity?: string
  status: InvestmentStatus
  start_date?: string
  target_completion?: string
  planned_total?: number
  actual_total: number
  strategic_rating?: number
  benefits: BenefitResponse[]
  spend_monthly: Array<{ month: string; planned: number; actual: number }>
  roi?: ROIMetrics
  benefit_count: number
  benefits_realized_pct?: number
  created_at: string
  updated_at: string
}

export interface PortfolioSummary {
  total_planned: number
  total_actual: number
  deployment_rate: number
  portfolio_roi?: number
  at_risk_count: number
}

export interface InvestmentListResponse {
  investments: InvestmentResponse[]
  total: number
  portfolio_summary: PortfolioSummary
}

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

export interface L2Summary {
  amount: number
  pct: number
  signal: VarianceSignal
}

export interface RTBSummary {
  total: number
  pct: number
  peer_median_pct?: number
  signal: VarianceSignal
  vs_plan_pct?: number
}

export interface CTBSummary {
  total: number
  pct: number
  peer_median_pct?: number
  signal: VarianceSignal
  deployment_rate?: number
}

export interface InvestmentSummary {
  active_count: number
  at_risk_count: number
  portfolio_roi?: number
  deployment_rate?: number
}

export interface DashboardSummary {
  org: Record<string, unknown>
  fiscal_year: number
  plan_id?: string
  plan_name?: string
  total_budget: number
  rtb: RTBSummary
  ctb: CTBSummary
  investments: InvestmentSummary
  by_l2: Record<string, L2Summary>
}

export interface TreemapNode {
  name: string
  value: number
  color?: string
  pct?: number
  children?: TreemapNode[]
}

export interface VarianceRecord {
  l2_category: string
  planned: number
  actual: number
  variance_amount: number
  variance_pct: number
  ytd_planned: number
  ytd_actual: number
  full_year_forecast?: number
  signal: VarianceSignal
  signal_reason?: string
}

export interface VarianceResponse {
  period: string
  plan_id?: string
  variances: VarianceRecord[]
}

// ---------------------------------------------------------------------------
// Benchmarks
// ---------------------------------------------------------------------------

export interface BenchmarkComparisonItem {
  l2_category: string
  org_pct?: number
  peer_p25?: number
  peer_median?: number
  peer_p75?: number
  signal: VarianceSignal
  insight?: string
}

export interface BenchmarkResponse {
  org: Record<string, unknown>
  benchmark_year: number
  benchmark_sector: string
  comparison: BenchmarkComparisonItem[]
}

export interface SectorBenchmarkItem {
  l2_category: string
  median_pct?: number
  p25_pct?: number
  p75_pct?: number
  mean_pct?: number
  n_companies?: number
}

export interface SectorBenchmarksResponse {
  sector: string
  year: number
  n_companies?: number
  benchmarks: SectorBenchmarkItem[]
}

// ---------------------------------------------------------------------------
// Upload
// ---------------------------------------------------------------------------

export interface UploadPreviewRow {
  row: number
  source_description: string
  source_cost_center?: string
  source_gl_account?: string
  amounts: Record<string, number>
  annual_total: number
  suggested_classification?: ClassificationResult
}

export interface UploadPreviewResponse {
  upload_id: string
  rows_detected: number
  columns_detected: string[]
  preview: UploadPreviewRow[]
  preview_count: number
}

// ---------------------------------------------------------------------------
// Decisions
// ---------------------------------------------------------------------------

export type DecisionSeverity = 'critical' | 'warning' | 'info'
export type DecisionStatus = 'new' | 'acknowledged' | 'in_progress' | 'resolved' | 'dismissed'

export interface Decision {
  id: string
  org_id: string
  investment_id?: string
  plan_id?: string
  category: string
  category_number: number
  severity: DecisionSeverity
  trigger_type?: string
  trigger_data: Record<string, unknown>
  title: string
  description: string
  recommended_action: string
  impact_estimate?: string
  owner?: string
  status: DecisionStatus
  resolved_at?: string
  resolved_by?: string
  resolution_notes?: string
  investment_name?: string
  created_at: string
  updated_at: string
}

export interface DecisionSummary {
  total: number
  active: number
  by_severity: Record<string, number>
  by_status: Record<string, number>
}

export interface DecisionScanResult {
  new_decisions: number
  decision_ids: string[]
}

// ---------------------------------------------------------------------------
// Agent types
// ---------------------------------------------------------------------------

export interface AgentMetric {
  label: string
  value: string | number
  type: 'ok' | 'info' | 'warning' | 'critical'
}

export interface AgentBriefing {
  generated_at: string
  org_name: string
  headline: string
  metrics_changed: AgentMetric[]
  signals_fired: Decision[]
  investments_update: Array<{ name: string; pct: number; issue: string }>
  upcoming: Array<{ id: string; name: string; target_completion: string; status: string }>
  recommended_actions: string[]
  narrative: string
}

export interface AgentBoardDeck {
  generated_at: string
  org_name: string
  period: string
  format: string
  content: string
  sections: string[]
}

export interface AgentAnswer {
  question: string
  answer: string
  confidence: 'high' | 'medium' | 'low'
  supporting_data: string[]
  follow_up_questions: string[]
  generated_at: string
}

export interface ScenarioChange {
  action: 'kill' | 'reallocate' | 'accelerate' | 'pause'
  investment_id?: string
  from_l2?: string
  to_l2?: string
  amount?: number
  additional_budget?: number
}

export interface AgentScenario {
  generated_at: string
  changes_analyzed: number
  current_state: { ctb_pct: number; rtb_pct: number; total_budget: number }
  projected_ctb_split: { new_ctb_pct?: number; new_rtb_pct?: number }
  projected_roi_impact: string
  benchmark_shift: string
  freed_resources: { budget_freed?: number; context?: string }
  risks: string[]
  narrative: string
}

export interface AgentReforecast {
  generated_at: string
  through_period: string
  annual_plan: number
  full_year_forecast: number
  variance_vs_plan: { amount: number; pct: number; direction: string }
  monthly_forecast: Array<{ period: string; projected_amount: number; basis: string }>
  variance_explanation: string
  risk_flags: string[]
  confidence: 'high' | 'medium' | 'low'
}

// ---------------------------------------------------------------------------
// Per-agent status & data types
// ---------------------------------------------------------------------------

export type AgentStatusLevel = 'active' | 'needs_attention' | 'idle'

export interface AgentInfo {
  id: string
  name: string
  emoji: string
  description: string
  href: string
  status: AgentStatusLevel
  last_run?: string
  key_metric?: string
}

// Scout
export interface ClassificationRecord {
  id: string
  source_description: string
  classified_l1: string
  classified_l2: string
  classified_l3: string
  classified_l4: string
  confidence: number
  confirmed: boolean
  created_at: string
}

export interface ScoutStats {
  total_classified: number
  confirmed_count: number
  accuracy_pct: number
  pending_review: number
  recent: ClassificationRecord[]
  // Data matching stats (optional — hydrated when matching data exists)
  matching_quality_score?: number
  matching_needs_review?: number
  matching_auto_matched?: number
}

// Compass
export interface CompassPosition {
  ctb_pct: number
  goldilocks_min: number
  goldilocks_max: number
  in_goldilocks: boolean
  peer_median_ctb: number
}

// Oracle early warning
export interface EarlyWarning {
  investment_id: string
  investment_name: string
  risk_type: string
  projected_miss_pct: number
  days_to_target: number
  message: string
}

export interface OracleData {
  reforecast: AgentReforecast | null
  early_warnings: EarlyWarning[]
}

// Scribe report
export interface GeneratedReport {
  id: string
  report_type: string
  period: string
  generated_at: string
  content: string
  format: string
}

// Guardian
export interface ComplianceFlag {
  id: string
  item_type: string
  item_name: string
  flag_type: string
  severity: 'critical' | 'warning' | 'info'
  message: string
  created_at: string
}

export interface PolicyRule {
  id: string
  name: string
  description: string
  threshold?: number
  enabled: boolean
}

export interface AuditEntry {
  id: string
  action: string
  actor: string
  item_type: string
  item_name: string
  timestamp: string
  details?: string
}

export interface ComplianceData {
  compliance_score: number
  flags: ComplianceFlag[]
  policy_rules: PolicyRule[]
  audit_log: AuditEntry[]
}

// Strategist
export interface SavedScenario {
  id: string
  name: string
  changes: ScenarioChange[]
  result?: AgentScenario
  created_at: string
}

export interface AgentStatus {
  org_id: string
  org_name: string
  status: string
  monitoring: {
    active_plan?: string
    fiscal_year?: number
    investments_tracked: number
    pending_signals: number
    signal_detectors: number
  }
  capabilities: string[]
  last_checked: string
}

// ---------------------------------------------------------------------------
// Connectors
// ---------------------------------------------------------------------------

export interface ConnectorConfig {
  id: string | null
  org_id: string | null
  connector_type: string
  status: 'disconnected' | 'connected' | 'syncing' | 'error'
  sync_frequency: string
  last_sync_at: string | null
  config: Record<string, unknown>
  created_at: string | null
  updated_at: string | null
  last_sync: {
    records_synced: number
    status: string
    completed_at: string
  } | null
}

export interface ConnectorMapping {
  id: string | null
  org_id: string | null
  connector_type: string
  source_type: string
  source_id: string
  source_name: string
  investment_id: string | null
  l2_category: string | null
  mapping_method: string
  confidence: number
  confirmed: boolean
  created_at: string | null
  updated_at: string | null
}

export interface CrmRevenueRow {
  id: string | null
  period: string
  source_product: string | null
  source_segment: string | null
  investment_id: string | null
  pipeline_amount: number
  closed_won_amount: number
  new_logos: number
  churned_amount: number
  avg_deal_size: number | null
  win_rate: number | null
  avg_cycle_days: number | null
}

export interface EffortRow {
  id: string | null
  period: string
  source_project: string | null
  source_epic: string | null
  investment_id: string | null
  hours_logged: number
  effort_cost: number
  story_points_completed: number
  issues_total: number
  issues_bugs: number
  issues_features: number
  issues_tasks: number
  velocity_trend: number | null
  backlog_growth: number
  completion_pct: number
}

export interface UnifiedCostView {
  investment_id: string
  investment_name: string
  l2_category: string | null
  status: string | null
  planned_cost: number
  gl_actual_cost: number
  effort_cost: number
  effort_hours: number
  revenue_pipeline: number
  revenue_closed: number
  new_logos: number
  churn_amount: number
  deployment_rate: number | null
  effort_efficiency: number | null
  roi_on_plan: number | null
  roi_on_effort: number | null
  pipeline_coverage: number | null
  discrepancies: string[]
  health_signals: Array<{
    category: number | null
    name: string
    description: string
    severity: 'critical' | 'warning' | 'info'
  }>
  signal: 'GREEN' | 'YELLOW' | 'RED'
}

export interface SyncResult {
  status: string
  records_synced: number
  records_mapped: number
  errors: Array<{ message: string; type: string }>
  started_at: string | null
  completed_at: string | null
}
