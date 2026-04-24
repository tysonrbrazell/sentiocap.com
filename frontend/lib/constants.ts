import type { L1Type, L2Category, L3Domain, VarianceSignal } from './types'

// ---------------------------------------------------------------------------
// Taxonomy
// ---------------------------------------------------------------------------

export const L1_TYPES = ['RTB', 'CTB'] as const

export const L2_CATEGORIES: L2Category[] = [
  'RTB-OPS',
  'RTB-MNT',
  'RTB-CMP',
  'RTB-SUP',
  'CTB-GRW',
  'CTB-TRN',
  'CTB-EFF',
  'CTB-INN',
]

export const L3_DOMAINS: L3Domain[] = [
  'TECH',
  'PPL',
  'COM',
  'PRD',
  'FAC',
  'FIN',
  'CRP',
  'DAT',
]

export const L2_LABELS: Record<L2Category, string> = {
  'RTB-OPS': 'Operations',
  'RTB-MNT': 'Maintenance',
  'RTB-CMP': 'Compliance',
  'RTB-SUP': 'Support',
  'CTB-GRW': 'Growth',
  'CTB-TRN': 'Transformation',
  'CTB-EFF': 'Efficiency',
  'CTB-INN': 'Innovation',
}

export const L3_LABELS: Record<L3Domain, string> = {
  TECH: 'Technology',
  PPL: 'People',
  COM: 'Commercial',
  PRD: 'Product',
  FAC: 'Facilities',
  FIN: 'Finance',
  CRP: 'Corporate',
  DAT: 'Data',
}

// ---------------------------------------------------------------------------
// Colors
// ---------------------------------------------------------------------------

export const L1_COLORS: Record<L1Type, string> = {
  RTB: '#3B82F6',
  CTB: '#22C55E',
}

export const L1_BG_COLORS: Record<L1Type, string> = {
  RTB: '#EFF6FF',
  CTB: '#F0FDF4',
}

export const L1_TEXT_COLORS: Record<L1Type, string> = {
  RTB: '#1D4ED8',
  CTB: '#15803D',
}

// RTB categories — blue shades
export const RTB_L2_COLORS: Record<string, string> = {
  'RTB-OPS': '#3B82F6',
  'RTB-MNT': '#60A5FA',
  'RTB-CMP': '#93C5FD',
  'RTB-SUP': '#BFDBFE',
}

// CTB categories — green shades
export const CTB_L2_COLORS: Record<string, string> = {
  'CTB-GRW': '#22C55E',
  'CTB-TRN': '#4ADE80',
  'CTB-EFF': '#86EFAC',
  'CTB-INN': '#BBF7D0',
}

export const L2_COLORS: Record<string, string> = {
  ...RTB_L2_COLORS,
  ...CTB_L2_COLORS,
}

export const SIGNAL_COLORS: Record<VarianceSignal, string> = {
  GREEN: '#22C55E',
  YELLOW: '#EAB308',
  RED: '#EF4444',
}

export const SIGNAL_BG_COLORS: Record<VarianceSignal, string> = {
  GREEN: '#F0FDF4',
  YELLOW: '#FEFCE8',
  RED: '#FEF2F2',
}

export const SIGNAL_TEXT_COLORS: Record<VarianceSignal, string> = {
  GREEN: '#15803D',
  YELLOW: '#92400E',
  RED: '#991B1B',
}

// ---------------------------------------------------------------------------
// Plan
// ---------------------------------------------------------------------------

export const PLAN_TYPE_LABELS: Record<string, string> = {
  annual_budget: 'Annual Budget',
  reforecast: 'Reforecast',
  scenario: 'Scenario',
}

export const PLAN_STATUS_LABELS: Record<string, string> = {
  draft: 'Draft',
  submitted: 'Submitted',
  approved: 'Approved',
  locked: 'Locked',
}

export const PLAN_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-700',
  submitted: 'bg-blue-100 text-blue-800',
  approved: 'bg-green-100 text-green-800',
  locked: 'bg-purple-100 text-purple-800',
}

// ---------------------------------------------------------------------------
// Investment
// ---------------------------------------------------------------------------

export const INVESTMENT_STATUS_LABELS: Record<string, string> = {
  proposed: 'Proposed',
  approved: 'Approved',
  in_progress: 'In Progress',
  completed: 'Completed',
  cancelled: 'Cancelled',
}

export const INVESTMENT_STATUS_COLORS: Record<string, string> = {
  proposed: 'bg-gray-100 text-gray-700',
  approved: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-emerald-100 text-emerald-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
}

export const BENEFIT_TYPE_OPTIONS = [
  'Cost Reduction',
  'Revenue Increase',
  'Risk Mitigation',
  'Productivity',
  'Other',
]

// ---------------------------------------------------------------------------
// Sectors
// ---------------------------------------------------------------------------

export const SECTORS = [
  'Technology',
  'Healthcare',
  'Financials',
  'Industrials',
  'Consumer Discretionary',
  'Consumer Staples',
  'Energy',
  'Utilities',
  'Real Estate',
  'Materials',
  'Communication Services',
]

export const REVENUE_BANDS = [
  'Under $100M',
  '$100M - $500M',
  '$500M - $1B',
  '$1B - $5B',
  '$5B - $25B',
  'Over $25B',
]
