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
