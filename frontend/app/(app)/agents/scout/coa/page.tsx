'use client'

import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Upload,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  BookOpen,
  ChevronDown,
  ChevronUp,
  Filter,
  ArrowLeft,
} from 'lucide-react'
import Link from 'next/link'
import { api } from '@/lib/api'
import type { CoAAccount, CoASummary, CoAStructure } from '@/lib/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'

// ---------------------------------------------------------------------------
// Confidence bar
// ---------------------------------------------------------------------------
function ConfidenceBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    score >= 0.8
      ? 'bg-green-500'
      : score >= 0.5
      ? 'bg-yellow-400'
      : 'bg-red-400'
  const label =
    score >= 0.8 ? 'text-green-700' : score >= 0.5 ? 'text-yellow-700' : 'text-red-600'
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className={`text-xs font-medium ${label}`}>{pct}%</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ERP badge
// ---------------------------------------------------------------------------
function ErpBadge({ erp }: { erp: string }) {
  const colors: Record<string, string> = {
    sap: 'bg-blue-100 text-blue-700 border-blue-200',
    oracle: 'bg-red-100 text-red-700 border-red-200',
    workday: 'bg-orange-100 text-orange-700 border-orange-200',
    netsuite: 'bg-purple-100 text-purple-700 border-purple-200',
    quickbooks: 'bg-green-100 text-green-700 border-green-200',
    unknown: 'bg-gray-100 text-gray-500 border-gray-200',
  }
  const cls = colors[erp.toLowerCase()] ?? colors.unknown
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      {erp.toUpperCase()}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Inline edit cell
// ---------------------------------------------------------------------------
function InlineEdit({
  value,
  onSave,
  placeholder,
}: {
  value?: string
  onSave: (val: string) => void
  placeholder?: string
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(value ?? '')

  if (editing) {
    return (
      <input
        autoFocus
        className="border border-blue-400 rounded px-1 py-0.5 text-xs w-20 focus:outline-none"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          onSave(draft)
          setEditing(false)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            onSave(draft)
            setEditing(false)
          }
          if (e.key === 'Escape') {
            setDraft(value ?? '')
            setEditing(false)
          }
        }}
      />
    )
  }

  return (
    <button
      onClick={() => setEditing(true)}
      className="px-1.5 py-0.5 rounded text-xs font-mono hover:bg-blue-50 hover:text-blue-700 transition-colors cursor-pointer"
      title="Click to edit"
    >
      {value || <span className="text-gray-300">{placeholder ?? '—'}</span>}
    </button>
  )
}

// ---------------------------------------------------------------------------
// Structure visualization
// ---------------------------------------------------------------------------
function StructureCard({ structure }: { structure: CoAStructure }) {
  const delimiter = structure.delimiter || 'none'
  const segs = structure.segment_definitions ?? []

  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-brand-accent" />
          <span className="text-sm font-semibold text-gray-700">Account Code Structure</span>
        </div>
        <ErpBadge erp={structure.detected_erp} />
      </div>

      <div className="flex items-center gap-1 flex-wrap mb-3">
        {segs.map((seg, i) => (
          <div key={i} className="flex items-center gap-1">
            <div className="bg-gray-100 border border-gray-200 rounded px-2 py-1 text-center min-w-[60px]">
              <div className="text-[10px] text-gray-400 uppercase tracking-wide">{seg.name.replace('_', ' ')}</div>
              <div className="text-xs font-mono font-medium text-gray-700">{seg.examples[0] ?? '????'}</div>
            </div>
            {i < segs.length - 1 && (
              <span className="text-sm text-gray-400 font-mono">{structure.delimiter || ' '}</span>
            )}
          </div>
        ))}
      </div>

      <div className="flex gap-4 text-xs text-gray-500 flex-wrap">
        <span>Delimiter: <code className="bg-gray-100 px-1 rounded">{delimiter}</code></span>
        <span>Segments: {structure.num_segments}</span>
        {structure.expense_range_start && (
          <span>Expense range: {structure.expense_range_start}–{structure.expense_range_end}</span>
        )}
        <span>
          Confidence: {Math.round((structure.detection_confidence ?? 0) * 100)}% ·{' '}
          {structure.samples_analyzed.toLocaleString()} samples
        </span>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function CoAPage() {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)

  // Filters
  const [filterClassified, setFilterClassified] = useState<boolean | undefined>(undefined)
  const [filterL1, setFilterL1] = useState('')
  const [filterL2, setFilterL2] = useState('')
  const [filterMinConf, setFilterMinConf] = useState<number | undefined>(undefined)
  const [page, setPage] = useState(1)
  const PER_PAGE = 100

  const { data: summary, isLoading: summaryLoading } = useQuery<CoASummary>({
    queryKey: ['coa-summary'],
    queryFn: () => api.coa.summary(),
    staleTime: 1000 * 60,
  })

  const { data: structure } = useQuery<CoAStructure>({
    queryKey: ['coa-structure'],
    queryFn: () => api.coa.structure(),
    staleTime: 1000 * 60 * 5,
    retry: false,
  })

  const { data: accountsData, isLoading: accountsLoading } = useQuery({
    queryKey: ['coa-accounts', filterClassified, filterL1, filterL2, filterMinConf, page],
    queryFn: () =>
      api.coa.list({
        is_expense: true,
        classified: filterClassified,
        l1: filterL1 || undefined,
        l2: filterL2 || undefined,
        min_confidence: filterMinConf,
        page,
        per_page: PER_PAGE,
      }),
    staleTime: 1000 * 30,
  })

  const { data: anomaliesData } = useQuery({
    queryKey: ['coa-anomalies'],
    queryFn: () => api.coa.anomalies(),
    staleTime: 1000 * 60,
  })

  const updateMutation = useMutation({
    mutationFn: ({
      accountCode,
      data,
    }: {
      accountCode: string
      data: { classified_l1?: string; classified_l2?: string; classified_l3?: string; classified_l4?: string }
    }) => api.coa.updateAccount(accountCode, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['coa-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['coa-summary'] })
    },
  })

  const reclassifyMutation = useMutation({
    mutationFn: () => api.coa.reclassify(),
    onSuccess: (result) => {
      setUploadMsg(result.message)
      queryClient.invalidateQueries({ queryKey: ['coa-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['coa-summary'] })
    },
  })

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    setUploadError(null)
    try {
      const result = await api.coa.analyze(file)
      const res = result as unknown as { classified_accounts?: number; new_accounts?: number }
      setUploadMsg(
        `Analysis complete — ${res.classified_accounts ?? 0} accounts classified, ${res.new_accounts ?? 0} new accounts learned.`
      )
      queryClient.invalidateQueries({ queryKey: ['coa-accounts'] })
      queryClient.invalidateQueries({ queryKey: ['coa-summary'] })
      queryClient.invalidateQueries({ queryKey: ['coa-structure'] })
    } catch (err: unknown) {
      setUploadError((err as Error).message ?? 'Upload failed')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const accounts: CoAAccount[] = accountsData?.accounts ?? []
  const totalAccounts = accountsData?.total ?? 0
  const totalPages = Math.ceil(totalAccounts / PER_PAGE)

  if (summaryLoading) return <PageSpinner />

  const coverage = summary?.classification_coverage ?? 0
  const coverageColor = coverage >= 80 ? 'text-green-600' : coverage >= 50 ? 'text-yellow-600' : 'text-red-600'

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAFAF8' }}>
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">

        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <Link href="/agents/scout" className="text-gray-400 hover:text-gray-600 transition-colors">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
                📒 Chart of Accounts
              </h1>
              <p className="text-sm text-gray-400 mt-1">
                Scout's learned GL structure · gets smarter with every upload
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={() => reclassifyMutation.mutate()}
              disabled={reclassifyMutation.isPending}
              className="flex items-center gap-2 text-sm"
            >
              <RefreshCw className={`w-4 h-4 ${reclassifyMutation.isPending ? 'animate-spin' : ''}`} />
              Re-classify All
            </Button>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              className="hidden"
              onChange={handleUpload}
            />
            <Button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-2 text-sm"
            >
              <Upload className="w-4 h-4" />
              {uploading ? 'Analyzing…' : 'Upload Trial Balance'}
            </Button>
          </div>
        </div>

        {uploadMsg && (
          <div className="flex items-center gap-2 text-sm text-green-700 bg-green-50 px-4 py-2.5 rounded-lg border border-green-200">
            <CheckCircle className="w-4 h-4 shrink-0" />
            {uploadMsg}
          </div>
        )}
        {uploadError && (
          <div className="flex items-center gap-2 text-sm text-red-700 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            {uploadError}
          </div>
        )}

        {/* Summary row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-gray-800">{(summary?.total_accounts ?? 0).toLocaleString()}</p>
            <p className="text-xs text-gray-500 mt-1">Total Accounts</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">{(summary?.expense_accounts ?? 0).toLocaleString()}</p>
            <p className="text-xs text-gray-500 mt-1">Expense Accounts</p>
          </Card>
          <Card className="p-4 text-center">
            <p className={`text-2xl font-bold ${coverageColor}`}>{coverage.toFixed(1)}%</p>
            <p className="text-xs text-gray-500 mt-1">Classification Coverage</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-yellow-600">{summary?.anomalies_detected ?? 0}</p>
            <p className="text-xs text-gray-500 mt-1">Anomalies Detected</p>
          </Card>
        </div>

        {/* Top categories */}
        {(summary?.top_categories?.length ?? 0) > 0 && (
          <Card className="p-4">
            <p className="text-sm font-semibold text-gray-700 mb-3">Top Spend Categories</p>
            <div className="flex flex-wrap gap-3">
              {summary!.top_categories.map((cat) => (
                <div key={cat.l2} className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                  <span className="font-mono text-xs font-semibold text-gray-700">{cat.l2}</span>
                  <span className="text-xs text-gray-500">${cat.amount.toLocaleString()}</span>
                  <span className="text-xs text-gray-400">({cat.pct}%)</span>
                </div>
              ))}
            </div>
          </Card>
        )}

        {/* Structure visualization */}
        {structure && <StructureCard structure={structure} />}

        {/* Filters */}
        <Card className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Filter className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-medium text-gray-700">Filter</span>
          </div>
          <div className="flex flex-wrap gap-3">
            <select
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
              value={filterClassified === undefined ? '' : String(filterClassified)}
              onChange={(e) => {
                setFilterClassified(e.target.value === '' ? undefined : e.target.value === 'true')
                setPage(1)
              }}
            >
              <option value="">All accounts</option>
              <option value="true">Classified</option>
              <option value="false">Unclassified</option>
            </select>

            <select
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
              value={filterL1}
              onChange={(e) => { setFilterL1(e.target.value); setPage(1) }}
            >
              <option value="">Any L1</option>
              <option value="RTB">RTB</option>
              <option value="CTB">CTB</option>
            </select>

            <input
              type="text"
              placeholder="Filter L2 (e.g. L2-INF)"
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-100 w-44"
              value={filterL2}
              onChange={(e) => { setFilterL2(e.target.value); setPage(1) }}
            />

            <select
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
              value={filterMinConf === undefined ? '' : String(filterMinConf)}
              onChange={(e) => {
                setFilterMinConf(e.target.value === '' ? undefined : parseFloat(e.target.value))
                setPage(1)
              }}
            >
              <option value="">Any confidence</option>
              <option value="0.8">High (≥80%)</option>
              <option value="0.5">Medium (≥50%)</option>
              <option value="0">Low (any)</option>
            </select>

            {(filterClassified !== undefined || filterL1 || filterL2 || filterMinConf !== undefined) && (
              <button
                onClick={() => {
                  setFilterClassified(undefined)
                  setFilterL1('')
                  setFilterL2('')
                  setFilterMinConf(undefined)
                  setPage(1)
                }}
                className="text-xs text-gray-400 hover:text-gray-600 underline"
              >
                Clear filters
              </button>
            )}
          </div>
        </Card>

        {/* Accounts table */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center justify-between">
              <span>Expense Accounts ({totalAccounts.toLocaleString()})</span>
              {accountsLoading && <RefreshCw className="w-4 h-4 animate-spin text-gray-400" />}
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {accounts.length === 0 && !accountsLoading ? (
              <div className="text-center py-16 text-gray-400 text-sm">
                {totalAccounts === 0
                  ? 'No accounts yet. Upload a trial balance to get started.'
                  : 'No accounts match the current filters.'}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-gray-100 bg-gray-50/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Code</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Account Name</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">L1</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">L2</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">L3</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">L4</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">Confidence</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">Seen</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Typical / Month</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {accounts.map((acct) => (
                      <AccountRow
                        key={acct.id}
                        account={acct}
                        onSave={(field, val) =>
                          updateMutation.mutate({
                            accountCode: acct.account_code,
                            data: { [field]: val || undefined },
                          })
                        }
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="text-sm px-3 py-1.5"
            >
              <ChevronUp className="w-4 h-4 rotate-90" />
            </Button>
            <span className="text-sm text-gray-500">
              Page {page} of {totalPages}
            </span>
            <Button
              variant="outline"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="text-sm px-3 py-1.5"
            >
              <ChevronDown className="w-4 h-4 rotate-90" />
            </Button>
          </div>
        )}

        {/* Anomalies section */}
        {(anomaliesData?.total ?? 0) > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2 text-yellow-700">
                <AlertTriangle className="w-4 h-4" />
                Anomalies ({anomaliesData!.total})
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-gray-100 bg-yellow-50/30">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Account</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Category</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Typical / Month</th>
                      <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">Times Seen</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {anomaliesData!.anomalies.map((anomaly) => (
                      <tr key={anomaly.account_code} className="hover:bg-yellow-50/30 transition-colors">
                        <td className="px-4 py-3">
                          <div className="font-mono text-xs font-medium text-gray-700">{anomaly.account_code}</div>
                          <div className="text-xs text-gray-500 max-w-xs truncate">{anomaly.account_name}</div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="font-mono text-xs text-gray-600">{anomaly.classified_l2 ?? '—'}</span>
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-gray-700">
                          ${anomaly.typical_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </td>
                        <td className="px-4 py-3 text-center text-xs text-gray-500">{anomaly.times_seen}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Account row (with inline edit)
// ---------------------------------------------------------------------------
function AccountRow({
  account,
  onSave,
}: {
  account: CoAAccount
  onSave: (field: string, val: string) => void
}) {
  const sourceLabel: Record<string, string> = {
    ai: '🤖',
    user: '✅',
    propagated: '↗',
    glossary: '📖',
    known_account: '💾',
    network: '🌐',
  }
  const sourceIcon = sourceLabel[account.classification_source] ?? '?'

  return (
    <tr className="hover:bg-gray-50 transition-colors group">
      <td className="px-4 py-2.5">
        <span className="font-mono text-xs font-medium text-gray-800">{account.account_code}</span>
      </td>
      <td className="px-4 py-2.5 max-w-xs">
        <span className="text-xs text-gray-700 truncate block" title={account.account_name}>
          {account.account_name}
        </span>
        {account.segment_cost_center && (
          <span className="text-[10px] text-gray-400">CC: {account.segment_cost_center}</span>
        )}
      </td>
      <td className="px-4 py-2.5 text-center">
        <InlineEdit
          value={account.classified_l1}
          onSave={(v) => onSave('classified_l1', v)}
          placeholder="L1"
        />
      </td>
      <td className="px-4 py-2.5 text-center">
        <InlineEdit
          value={account.classified_l2}
          onSave={(v) => onSave('classified_l2', v)}
          placeholder="L2"
        />
      </td>
      <td className="px-4 py-2.5 text-center">
        <InlineEdit
          value={account.classified_l3}
          onSave={(v) => onSave('classified_l3', v)}
          placeholder="L3"
        />
      </td>
      <td className="px-4 py-2.5 text-center">
        <InlineEdit
          value={account.classified_l4}
          onSave={(v) => onSave('classified_l4', v)}
          placeholder="L4"
        />
      </td>
      <td className="px-4 py-2.5 text-center">
        <div className="flex flex-col items-center gap-0.5">
          <ConfidenceBar score={account.classification_confidence} />
          <span className="text-[10px] text-gray-400">{sourceIcon}</span>
        </div>
      </td>
      <td className="px-4 py-2.5 text-center">
        <span className="text-xs text-gray-500">{account.times_seen}</span>
      </td>
      <td className="px-4 py-2.5 text-right font-mono text-xs text-gray-600">
        {account.typical_monthly_amount != null
          ? `$${account.typical_monthly_amount.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
          : '—'}
      </td>
    </tr>
  )
}
