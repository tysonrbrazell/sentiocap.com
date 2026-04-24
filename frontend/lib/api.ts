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

  decisions: {
    list: (queryString?: string) =>
      get<Decision[]>(`/api/decisions${queryString ? '?' + queryString : ''}`),
    get: (id: string) => get<Decision>(`/api/decisions/${id}`),
    summary: () => get<DecisionSummary>('/api/decisions/summary'),
    scan: () => post<DecisionScanResult>('/api/decisions/scan'),
    update: (id: string, data: { status?: string; owner?: string; resolution_notes?: string }) =>
      request<Decision>(`/api/decisions/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  },
}
