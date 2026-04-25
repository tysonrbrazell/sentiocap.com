import { getAuthToken } from './utils'
import type {
  TokenResponse,
  RegisterResponse,
  LoginRequest,
  RegisterRequest,
  PlanCreate,
  PlanResponse,
  PlanListResponse,
  LineItemUpdate,
  PlanLineItemResponse,
  ClassifyPlanResponse,
  InvestmentCreate,
  InvestmentResponse,
  InvestmentListResponse,
  DashboardSummary,
  TreemapNode,
  VarianceResponse,
  BenchmarkResponse,
  SectorBenchmarksResponse,
  OrgResponse,
  OrgUpdate,
  UserResponse,
  JobStatus,
  UploadPreviewResponse,
  Decision,
  DecisionSummary,
  DecisionScanResult,
  AgentBriefing,
  AgentBoardDeck,
  AgentAnswer,
  AgentScenario,
  AgentReforecast,
  AgentStatus,
  ScenarioChange,
  ScoutStats,
  CompassPosition,
  OracleData,
  GeneratedReport,
  ComplianceData,
  SavedScenario,
  AgentInfo,
  ConnectorConfig,
  ConnectorMapping,
  CrmRevenueRow,
  EffortRow,
  UnifiedCostView,
  SyncResult,
} from './types'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

async function request<T>(
  path: string,
  options: RequestInit = {},
  skipAuth = false
): Promise<T> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (!skipAuth && token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(error.detail || `Request failed: ${res.status}`)
  }

  // Handle 204 No Content
  if (res.status === 204) return {} as T

  return res.json()
}

function get<T>(path: string, skipAuth = false): Promise<T> {
  return request<T>(path, { method: 'GET' }, skipAuth)
}

function post<T>(path: string, body?: unknown, skipAuth = false): Promise<T> {
  return request<T>(
    path,
    { method: 'POST', body: body ? JSON.stringify(body) : undefined },
    skipAuth
  )
}

function patch<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'PATCH',
    body: body ? JSON.stringify(body) : undefined,
  })
}

function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: 'DELETE' })
}

async function upload<T>(path: string, file: File, extraFields?: Record<string, string>): Promise<T> {
  const token = getAuthToken()
  const formData = new FormData()
  formData.append('file', file)
  if (extraFields) {
    for (const [key, val] of Object.entries(extraFields)) {
      formData.append(key, val)
    }
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || `Upload failed: ${res.status}`)
  }

  return res.json()
}

// ---------------------------------------------------------------------------
// API Surface
// ---------------------------------------------------------------------------

export const api = {
  auth: {
    login: (data: LoginRequest) =>
      post<TokenResponse>('/api/auth/login', data, true),
    register: (data: RegisterRequest) =>
      post<RegisterResponse>('/api/auth/register', data, true),
    me: () => get<UserResponse>('/api/auth/me'),
  },

  organizations: {
    get: (id: string) => get<OrgResponse>(`/api/organizations/${id}`),
    update: (id: string, data: OrgUpdate) =>
      patch<OrgResponse>(`/api/organizations/${id}`, data),
    members: (id: string) => get<UserResponse[]>(`/api/organizations/${id}/members`),
    inviteMember: (id: string, data: { email: string; role: string }) =>
      post<UserResponse>(`/api/organizations/${id}/members`, data),
    removeMember: (orgId: string, userId: string) =>
      del<void>(`/api/organizations/${orgId}/members/${userId}`),
  },

  plans: {
    list: () => get<PlanListResponse>('/api/plans'),
    create: (data: PlanCreate) => post<PlanResponse>('/api/plans', data),
    get: (id: string, page = 1, limit = 50) =>
      get<PlanResponse>(`/api/plans/${id}?page=${page}&limit=${limit}`),
    update: (id: string, data: Partial<PlanCreate>) =>
      patch<PlanResponse>(`/api/plans/${id}`, data),
    delete: (id: string) => del<void>(`/api/plans/${id}`),
    approve: (id: string, notes?: string) =>
      post<PlanResponse>(`/api/plans/${id}/approve`, { notes }),
    classify: (id: string, mode = 'unclassified_only') =>
      post<ClassifyPlanResponse>(`/api/plans/${id}/classify`, { mode }),
    uploadFile: (id: string, file: File) =>
      upload<UploadPreviewResponse>(`/api/plans/${id}/upload`, file),
  },

  lineItems: {
    list: (planId: string, params?: Record<string, string>) => {
      const qs = params ? '?' + new URLSearchParams(params).toString() : ''
      return get<{ items: PlanLineItemResponse[]; total: number }>(`/api/plans/${planId}/line-items${qs}`)
    },
    update: (planId: string, itemId: string, data: LineItemUpdate) =>
      patch<PlanLineItemResponse>(`/api/plans/${planId}/line-items/${itemId}`, data),
  },

  investments: {
    list: () => get<InvestmentListResponse>('/api/investments'),
    create: (data: InvestmentCreate) =>
      post<InvestmentResponse>('/api/investments', data),
    get: (id: string) => get<InvestmentResponse>(`/api/investments/${id}`),
    update: (id: string, data: Partial<InvestmentCreate>) =>
      patch<InvestmentResponse>(`/api/investments/${id}`, data),
    delete: (id: string) => del<void>(`/api/investments/${id}`),
    getROI: (id: string) => get<unknown>(`/api/investments/${id}/roi`),
  },

  dashboard: {
    summary: () => get<DashboardSummary>('/api/dashboard/summary'),
    treemap: () => get<{ nodes: TreemapNode[] }>('/api/dashboard/treemap'),
    variance: () => get<VarianceResponse>('/api/dashboard/variance'),
  },

  benchmarks: {
    compare: (sector: string, revenueBand?: string) => {
      const qs = new URLSearchParams({ sector })
      if (revenueBand) qs.set('revenue_band', revenueBand)
      return get<BenchmarkResponse>(`/api/benchmarks?${qs}`)
    },
    sector: (sector: string) =>
      get<SectorBenchmarksResponse>(`/api/benchmarks/sector?sector=${encodeURIComponent(sector)}`),
  },

  jobs: {
    status: (jobId: string) => get<JobStatus>(`/api/jobs/${jobId}`),
  },

  agent: {
    briefing: () => post<AgentBriefing>('/api/agent/briefing'),
    boardDeck: (period: string, format = 'markdown') =>
      post<AgentBoardDeck>('/api/agent/board-deck', { period, format }),
    ask: (question: string) => post<AgentAnswer>('/api/agent/ask', { question }),
    simulate: (changes: ScenarioChange[]) =>
      post<AgentScenario>('/api/agent/simulate', { changes }),
    reforecast: (through_period: string) =>
      post<AgentReforecast>('/api/agent/reforecast', { through_period }),
    status: () => get<AgentStatus>('/api/agent/status'),
  },

  decisions: {
    list: (queryString?: string) =>
      get<Decision[]>(`/api/decisions${queryString ? '?' + queryString : ''}`),
    get: (id: string) => get<Decision>(`/api/decisions/${id}`),
    summary: () => get<DecisionSummary>('/api/decisions/summary'),
    scan: () => post<DecisionScanResult>('/api/decisions/scan'),
    update: (id: string, data: { status?: string; owner?: string; resolution_notes?: string }) =>
      request<Decision>(`/api/decisions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },

  // Per-agent APIs (extend as backend grows)
  scout: {
    stats: () => get<ScoutStats>('/api/agent/scout/stats'),
    uploadDocument: (file: File) => upload<{ job_id: string; message: string }>('/api/agent/scout/upload', file),
    queue: () => get<{ items: Array<{ id: string; description: string; confidence: number }> }>('/api/agent/scout/queue'),
  },

  compass: {
    position: () => get<CompassPosition>('/api/agent/compass/position'),
  },

  oracle: {
    data: (period?: string) => {
      const qs = period ? `?period=${period}` : ''
      return get<OracleData>(`/api/agent/oracle${qs}`)
    },
  },

  scribe: {
    reports: () => get<GeneratedReport[]>('/api/agent/scribe/reports'),
    generateBoardDeck: (period: string, format = 'markdown') =>
      post<AgentBoardDeck>('/api/agent/board-deck', { period, format }),
    generateBriefing: (period: string) =>
      post<GeneratedReport>('/api/agent/scribe/briefing', { period }),
  },

  guardian: {
    data: () => get<ComplianceData>('/api/agent/guardian'),
    resolveFlag: (flagId: string) => post<{ ok: boolean }>(`/api/agent/guardian/flags/${flagId}/resolve`),
  },

  strategist: {
    scenarios: () => get<SavedScenario[]>('/api/agent/strategist/scenarios'),
    saveScenario: (name: string, changes: ScenarioChange[], result?: AgentScenario) =>
      post<SavedScenario>('/api/agent/strategist/scenarios', { name, changes, result }),
    deleteScenario: (id: string) => del<void>(`/api/agent/strategist/scenarios/${id}`),
  },

  agents: {
    all: () => get<AgentInfo[]>('/api/agent/all'),
  },

  connectors: {
    list: () => get<ConnectorConfig[]>('/api/connectors'),
    connect: (type: string) =>
      post<{ status: string; connector: ConnectorConfig }>(`/api/connectors/${type}/connect`, { mock: true }),
    disconnect: (type: string) =>
      post<{ status: string }>(`/api/connectors/${type}/disconnect`, {}),
    sync: (type: string) => post<SyncResult>(`/api/connectors/${type}/sync`, {}),
    status: (type: string) => get<ConnectorConfig>(`/api/connectors/${type}/status`),
    revenueData: (type: string, period?: string) => {
      const qs = period ? `?period=${period}` : ''
      return get<CrmRevenueRow[]>(`/api/connectors/${type}/data/revenue${qs}`)
    },
    effortData: (type: string, period?: string) => {
      const qs = period ? `?period=${period}` : ''
      return get<EffortRow[]>(`/api/connectors/${type}/data/effort${qs}`)
    },
    mappings: (type: string) => get<ConnectorMapping[]>(`/api/connectors/${type}/mappings`),
    updateMapping: (type: string, id: string, data: Partial<ConnectorMapping>) =>
      request<ConnectorMapping>(`/api/connectors/${type}/mappings/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    unifiedCost: () => get<UnifiedCostView[]>('/api/connectors/unified-cost'),
  },

  matching: {
    preview: (sourceSystem: string, items?: unknown[]) =>
      post<{ results: unknown[]; total: number; needs_review: number; auto_matched: number; unmatched: number }>(
        '/api/matching/preview',
        { source_system: sourceSystem, ...(items ? { items } : {}) }
      ),
    confirm: (body: {
      source_id: string
      source_system: string
      source_name: string
      target_id: string
      target_name: string
      target_type: string
      allocation_pct?: number
    }) => post<{ status: string }>('/api/matching/confirm', body),
    confirmBatch: (sourceSystem: string, matches: unknown[]) =>
      post<{ confirmed: string[]; errors: unknown[]; total: number }>(
        '/api/matching/confirm-batch',
        { source_system: sourceSystem, matches }
      ),
    split: (body: {
      source_id: string
      source_name: string
      source_system: string
      splits: unknown[]
    }) => post<{ status: string }>('/api/matching/split', body),
    markRtb: (body: {
      source_id: string
      source_name: string
      source_system: string
      l2_category: string
    }) => post<{ status: string }>('/api/matching/mark-rtb', body),
    dismiss: (sourceId: string, sourceSystem: string, sourceName?: string) =>
      post<{ status: string }>('/api/matching/dismiss', {
        source_id: sourceId,
        source_system: sourceSystem,
        source_name: sourceName ?? '',
      }),
    stats: () => get<{
      total: number
      confirmed: number
      auto_matched: number
      needs_review: number
      unmatched: number
      quality_score: number
      by_system: Record<string, { total: number; confirmed: number }>
    }>('/api/matching/stats'),
    autoMatch: (sourceSystem: string, threshold?: number) =>
      post<{ auto_matched: unknown[]; needs_review: unknown[]; unmatched: unknown[]; stats: unknown }>(
        '/api/matching/auto-match',
        { source_system: sourceSystem, auto_confirm_threshold: threshold ?? 0.85 }
      ),
  },
}
