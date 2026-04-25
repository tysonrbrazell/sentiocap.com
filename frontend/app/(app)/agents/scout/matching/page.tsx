'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { CheckCircle, XCircle, AlertCircle, Zap, Undo2, Search, Plus, ArrowLeft } from 'lucide-react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MatchCandidate {
  target_id: string
  target_name: string
  target_type: 'investment' | 'rtb_category'
  confidence: number
  match_method: string
  reasoning: string
  allocation_pct: number
}

interface MatchResult {
  source_id: string
  source_name: string
  source_type: string
  source_system: string
  match_status: 'auto_matched' | 'needs_review' | 'unmatched'
  needs_review: boolean
  best_match: MatchCandidate | null
  candidates: MatchCandidate[]
}

interface MatchStats {
  total: number
  confirmed: number
  auto_matched: number
  needs_review: number
  unmatched: number
  quality_score: number
  by_system: Record<string, { total: number; confirmed: number }>
}

interface SplitEntry {
  target_id: string
  target_name: string
  target_type: string
  allocation_pct: number
}

const RTB_L2_OPTIONS = [
  { value: 'RTB-OPS', label: 'RTB-OPS — Operations' },
  { value: 'RTB-MNT', label: 'RTB-MNT — Maintenance' },
  { value: 'RTB-CMP', label: 'RTB-CMP — Compliance' },
  { value: 'RTB-SUP', label: 'RTB-SUP — Support' },
]

// ---------------------------------------------------------------------------
// Confidence bar
// ---------------------------------------------------------------------------

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color =
    value >= 0.85 ? '#4A7C59' : value >= 0.65 ? '#D97706' : '#DC2626'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, backgroundColor: color }}
        />
      </div>
      <span className="text-xs font-medium w-9 text-right" style={{ color }}>
        {pct}%
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// System badge
// ---------------------------------------------------------------------------

function SystemBadge({ system }: { system: string }) {
  const styles: Record<string, string> = {
    salesforce: 'bg-blue-100 text-blue-700',
    jira: 'bg-purple-100 text-purple-700',
    erp: 'bg-gray-100 text-gray-700',
  }
  return (
    <span
      className={`inline-flex px-1.5 py-0.5 rounded text-xs font-semibold uppercase tracking-wide ${
        styles[system] ?? 'bg-gray-100 text-gray-600'
      }`}
    >
      {system}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Circular quality score
// ---------------------------------------------------------------------------

function QualityRing({ score }: { score: number }) {
  const r = 36
  const circ = 2 * Math.PI * r
  const offset = circ - (score / 100) * circ
  const color = score >= 80 ? '#4A7C59' : score >= 60 ? '#D97706' : '#DC2626'

  return (
    <svg width="96" height="96" viewBox="0 0 96 96">
      <circle cx="48" cy="48" r={r} fill="none" stroke="#E5E7EB" strokeWidth="8" />
      <circle
        cx="48"
        cy="48"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="8"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform="rotate(-90 48 48)"
        style={{ transition: 'stroke-dashoffset 0.6s ease' }}
      />
      <text x="48" y="48" dominantBaseline="middle" textAnchor="middle" fontSize="16" fontWeight="700" fill={color}>
        {Math.round(score)}%
      </text>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Card: Needs Review
// ---------------------------------------------------------------------------

function ReviewCard({
  item,
  onConfirm,
  onRtb,
  onDismiss,
}: {
  item: MatchResult
  onConfirm: (sourceId: string, sourceSystem: string, sourceName: string, candidate: MatchCandidate) => void
  onRtb: (sourceId: string, sourceSystem: string, sourceName: string, l2: string) => void
  onDismiss: (sourceId: string, sourceSystem: string) => void
}) {
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [showSplit, setShowSplit] = useState(false)
  const [showRtb, setShowRtb] = useState(false)
  const [rtbL2, setRtbL2] = useState('RTB-OPS')
  const [splits, setSplits] = useState<SplitEntry[]>(
    item.candidates.slice(0, 2).map((c, i) => ({
      target_id: c.target_id,
      target_name: c.target_name,
      target_type: c.target_type,
      allocation_pct: i === 0 ? 60 : 40,
    }))
  )

  const topCandidates = item.candidates.slice(0, 3)

  return (
    <div className="bg-white rounded-xl border border-yellow-200 p-4 space-y-3 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-800 text-sm truncate">{item.source_name}</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <SystemBadge system={item.source_system} />
            <span className="text-xs text-gray-400">{item.source_type}</span>
          </div>
        </div>
      </div>

      {/* Candidates */}
      {!showSplit && !showRtb && (
        <div className="space-y-2">
          {topCandidates.map((c, i) => (
            <label
              key={c.target_id}
              className={`flex items-start gap-2.5 p-2.5 rounded-lg cursor-pointer border transition-colors ${
                selectedIdx === i
                  ? 'border-brand-accent bg-green-50'
                  : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'
              }`}
            >
              <input
                type="radio"
                name={`candidate-${item.source_id}`}
                checked={selectedIdx === i}
                onChange={() => setSelectedIdx(i)}
                className="mt-0.5 accent-[#4A7C59]"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-800 truncate">{c.target_name}</p>
                <p className="text-xs text-gray-400 truncate">{c.reasoning}</p>
                <ConfidenceBar value={c.confidence} />
              </div>
            </label>
          ))}
          {topCandidates.length === 0 && (
            <p className="text-xs text-gray-400 text-center py-2">No candidates found</p>
          )}
        </div>
      )}

      {/* Split view */}
      {showSplit && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-600">Split allocation (must sum to 100%)</p>
          {splits.map((s, i) => (
            <div key={s.target_id} className="flex items-center gap-2">
              <span className="text-xs text-gray-700 flex-1 truncate">{s.target_name}</span>
              <input
                type="number"
                min={0}
                max={100}
                value={s.allocation_pct}
                onChange={e => {
                  const updated = [...splits]
                  updated[i] = { ...updated[i], allocation_pct: parseFloat(e.target.value) || 0 }
                  setSplits(updated)
                }}
                className="w-16 text-xs border border-gray-200 rounded px-1.5 py-1 text-right"
              />
              <span className="text-xs text-gray-400">%</span>
            </div>
          ))}
          <p className="text-xs text-gray-400">
            Total: {splits.reduce((s, e) => s + e.allocation_pct, 0).toFixed(0)}%
          </p>
        </div>
      )}

      {/* RTB selector */}
      {showRtb && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-gray-600">Mark as operational (RTB)</p>
          <select
            value={rtbL2}
            onChange={e => setRtbL2(e.target.value)}
            className="w-full text-xs border border-gray-200 rounded px-2 py-1.5 bg-white"
          >
            {RTB_L2_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-1.5 flex-wrap pt-1">
        {!showSplit && !showRtb && (
          <>
            <Button
              size="sm"
              onClick={() => {
                const c = topCandidates[selectedIdx]
                if (c) onConfirm(item.source_id, item.source_system, item.source_name, c)
              }}
              disabled={topCandidates.length === 0}
              className="text-xs py-1 px-2.5"
            >
              Confirm
            </Button>
            <button
              onClick={() => setShowSplit(true)}
              className="text-xs px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50"
            >
              Split
            </button>
            <button
              onClick={() => setShowRtb(true)}
              className="text-xs px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50"
            >
              RTB
            </button>
            <button
              onClick={() => onDismiss(item.source_id, item.source_system)}
              className="text-xs px-2.5 py-1 rounded text-gray-400 hover:text-gray-600 ml-auto"
            >
              Skip
            </button>
          </>
        )}

        {showSplit && (
          <>
            <Button
              size="sm"
              onClick={() => {
                const total = splits.reduce((s, e) => s + e.allocation_pct, 0)
                if (Math.abs(total - 100) > 1) return alert('Allocations must sum to 100%')
                // Confirm first split, rest handled by split endpoint separately
                splits.forEach(s => {
                  const c: MatchCandidate = {
                    target_id: s.target_id,
                    target_name: s.target_name,
                    target_type: s.target_type as 'investment' | 'rtb_category',
                    confidence: 1.0,
                    match_method: 'manual_split',
                    reasoning: 'Manual split allocation',
                    allocation_pct: s.allocation_pct,
                  }
                  onConfirm(item.source_id, item.source_system, item.source_name, c)
                })
                setShowSplit(false)
              }}
              className="text-xs py-1 px-2.5"
            >
              Save Split
            </Button>
            <button
              onClick={() => setShowSplit(false)}
              className="text-xs px-2 py-1 text-gray-400 hover:text-gray-600"
            >
              Cancel
            </button>
          </>
        )}

        {showRtb && (
          <>
            <Button
              size="sm"
              onClick={() => {
                onRtb(item.source_id, item.source_system, item.source_name, rtbL2)
                setShowRtb(false)
              }}
              className="text-xs py-1 px-2.5"
            >
              Mark RTB
            </Button>
            <button
              onClick={() => setShowRtb(false)}
              className="text-xs px-2 py-1 text-gray-400 hover:text-gray-600"
            >
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card: Auto-matched
// ---------------------------------------------------------------------------

function AutoMatchedCard({
  item,
  onUndo,
}: {
  item: MatchResult
  onUndo: (sourceId: string, sourceSystem: string) => void
}) {
  return (
    <div className="bg-white rounded-xl border border-green-200 p-3.5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{item.source_name}</p>
          <div className="flex items-center gap-1 mt-0.5 flex-wrap">
            <SystemBadge system={item.source_system} />
            {item.best_match && (
              <>
                <span className="text-xs text-gray-400">→</span>
                <span className="text-xs text-gray-600 font-medium truncate max-w-[140px]">
                  {item.best_match.target_name}
                </span>
              </>
            )}
          </div>
          {item.best_match && (
            <div className="mt-1.5">
              <ConfidenceBar value={item.best_match.confidence} />
            </div>
          )}
        </div>
        <button
          onClick={() => onUndo(item.source_id, item.source_system)}
          className="shrink-0 text-gray-400 hover:text-gray-600 p-1 rounded hover:bg-gray-50"
          title="Move back to review"
        >
          <Undo2 className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card: Unmatched
// ---------------------------------------------------------------------------

function UnmatchedCard({
  item,
  onRtb,
  onDismiss,
}: {
  item: MatchResult
  onRtb: (sourceId: string, sourceSystem: string, sourceName: string, l2: string) => void
  onDismiss: (sourceId: string, sourceSystem: string) => void
}) {
  const [showRtb, setShowRtb] = useState(false)
  const [rtbL2, setRtbL2] = useState('RTB-OPS')

  return (
    <div className="bg-white rounded-xl border border-red-200 p-3.5 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{item.source_name}</p>
          <div className="flex items-center gap-1.5 mt-0.5">
            <SystemBadge system={item.source_system} />
            <span className="text-xs text-red-500">No match found</span>
          </div>
        </div>
      </div>

      {showRtb && (
        <div className="mt-2 space-y-2">
          <select
            value={rtbL2}
            onChange={e => setRtbL2(e.target.value)}
            className="w-full text-xs border border-gray-200 rounded px-2 py-1.5 bg-white"
          >
            {RTB_L2_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      <div className="flex items-center gap-1.5 mt-2.5 flex-wrap">
        <button className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50">
          <Search className="w-3 h-3" />
          Search
        </button>
        <button className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50">
          <Plus className="w-3 h-3" />
          New Investment
        </button>
        {!showRtb ? (
          <button
            onClick={() => setShowRtb(true)}
            className="text-xs px-2 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-50"
          >
            RTB
          </button>
        ) : (
          <>
            <Button
              size="sm"
              onClick={() => {
                onRtb(item.source_id, item.source_system, item.source_name, rtbL2)
                setShowRtb(false)
              }}
              className="text-xs py-1 px-2.5"
            >
              Confirm RTB
            </Button>
            <button onClick={() => setShowRtb(false)} className="text-xs text-gray-400 px-1">✕</button>
          </>
        )}
        <button
          onClick={() => onDismiss(item.source_id, item.source_system)}
          className="text-xs px-2 py-1 rounded text-gray-400 hover:text-gray-600 ml-auto"
        >
          Dismiss
        </button>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Column header
// ---------------------------------------------------------------------------

function ColumnHeader({
  label,
  count,
  color,
  icon,
}: {
  label: string
  count: number
  color: string
  icon: React.ReactNode
}) {
  return (
    <div
      className="flex items-center justify-between px-4 py-2.5 rounded-t-xl border-b"
      style={{ backgroundColor: color + '15', borderColor: color + '30' }}
    >
      <div className="flex items-center gap-2">
        <span style={{ color }}>{icon}</span>
        <span className="font-semibold text-sm" style={{ color }}>
          {label}
        </span>
      </div>
      <span
        className="text-xs font-bold px-2 py-0.5 rounded-full"
        style={{ backgroundColor: color + '20', color }}
      >
        {count}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function MatchingPage() {
  const queryClient = useQueryClient()
  const [activeSystem, setActiveSystem] = useState<'salesforce' | 'jira'>('salesforce')
  const [previewResults, setPreviewResults] = useState<MatchResult[]>([])
  const [isPreviewing, setIsPreviewing] = useState(false)

  // Stats
  const { data: stats } = useQuery<MatchStats>({
    queryKey: ['matching-stats'],
    queryFn: () => api.matching.stats() as Promise<MatchStats>,
    staleTime: 1000 * 30,
  })

  // Preview mutation
  const previewMutation = useMutation({
    mutationFn: (sourceSystem: string) =>
      api.matching.preview(sourceSystem).then(r => (r.results ?? []) as MatchResult[]),
    onSuccess: (data: MatchResult[]) => {
      setPreviewResults(data)
      setIsPreviewing(false)
    },
    onError: () => setIsPreviewing(false),
  })

  // Auto-match mutation
  const autoMatchMutation = useMutation({
    mutationFn: () => api.matching.autoMatch(activeSystem),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matching-stats'] })
      handlePreview()
    },
  })

  // Confirm mutation
  const confirmMutation = useMutation({
    mutationFn: (body: Parameters<typeof api.matching.confirm>[0]) =>
      api.matching.confirm(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matching-stats'] })
    },
  })

  // RTB mutation
  const rtbMutation = useMutation({
    mutationFn: (body: Parameters<typeof api.matching.markRtb>[0]) =>
      api.matching.markRtb(body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matching-stats'] })
    },
  })

  // Dismiss mutation
  const dismissMutation = useMutation({
    mutationFn: ({ sourceId, sourceSystem }: { sourceId: string; sourceSystem: string }) =>
      api.matching.dismiss(sourceId, sourceSystem),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['matching-stats'] })
    },
  })

  function handlePreview() {
    setIsPreviewing(true)
    previewMutation.mutate(activeSystem)
  }

  function handleConfirm(
    sourceId: string,
    sourceSystem: string,
    sourceName: string,
    candidate: MatchCandidate
  ) {
    confirmMutation.mutate({
      source_id: sourceId,
      source_system: sourceSystem,
      source_name: sourceName,
      target_id: candidate.target_id,
      target_name: candidate.target_name,
      target_type: candidate.target_type,
      allocation_pct: candidate.allocation_pct,
    })
    setPreviewResults(prev => prev.filter(r => r.source_id !== sourceId))
  }

  function handleRtb(sourceId: string, sourceSystem: string, sourceName: string, l2: string) {
    rtbMutation.mutate({ source_id: sourceId, source_system: sourceSystem, source_name: sourceName, l2_category: l2 })
    setPreviewResults(prev => prev.filter(r => r.source_id !== sourceId))
  }

  function handleDismiss(sourceId: string, sourceSystem: string) {
    dismissMutation.mutate({ sourceId, sourceSystem })
    setPreviewResults(prev => prev.filter(r => r.source_id !== sourceId))
  }

  function handleUndo(sourceId: string, _sourceSystem: string) {
    // Move auto-matched back to needs_review
    setPreviewResults(prev =>
      prev.map(r =>
        r.source_id === sourceId
          ? { ...r, match_status: 'needs_review', needs_review: true }
          : r
      )
    )
  }

  const needsReview = previewResults.filter(r => r.match_status === 'needs_review')
  const autoMatched = previewResults.filter(r => r.match_status === 'auto_matched')
  const unmatched = previewResults.filter(r => r.match_status === 'unmatched')

  const totalPreview = previewResults.length
  const resolvedCount = autoMatched.length
  const futureScore =
    stats && totalPreview > 0
      ? Math.min(
          100,
          ((stats.confirmed + stats.auto_matched + resolvedCount) /
            Math.max(stats.total + totalPreview, 1)) *
            100
        )
      : stats?.quality_score ?? 0

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAFAF8' }}>
      <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Link
                href="/agents/scout"
                className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
              >
                <ArrowLeft className="w-3 h-3" />
                Scout
              </Link>
            </div>
            <h1 className="text-2xl font-bold text-gray-900">Data Matching</h1>
            <p className="text-sm text-gray-400 mt-0.5">
              Resolve messy enterprise data — map external items to investments
            </p>
          </div>

          {/* System toggle */}
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              {(['salesforce', 'jira'] as const).map(sys => (
                <button
                  key={sys}
                  onClick={() => setActiveSystem(sys)}
                  className={`px-3 py-1.5 font-medium capitalize transition-colors ${
                    activeSystem === sys
                      ? 'bg-gray-900 text-white'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {sys}
                </button>
              ))}
            </div>
            <Button onClick={handlePreview} disabled={isPreviewing} className="flex items-center gap-2">
              {isPreviewing ? 'Loading…' : 'Preview Matches'}
            </Button>
          </div>
        </div>

        {/* Quality Score Bar */}
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center gap-6">
              {/* Circular ring */}
              <div className="shrink-0">
                <QualityRing score={stats?.quality_score ?? 0} />
              </div>

              {/* Breakdown */}
              <div className="flex-1 grid grid-cols-4 gap-4">
                <div className="text-center">
                  <p className="text-2xl font-bold text-green-600">{stats?.confirmed ?? 0}</p>
                  <p className="text-xs text-gray-400 mt-0.5">Confirmed</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold" style={{ color: '#4A7C59' }}>
                    {stats?.auto_matched ?? 0}
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">Auto-matched</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-yellow-600">{stats?.needs_review ?? 0}</p>
                  <p className="text-xs text-gray-400 mt-0.5">Needs Review</p>
                </div>
                <div className="text-center">
                  <p className="text-2xl font-bold text-red-500">{stats?.unmatched ?? 0}</p>
                  <p className="text-xs text-gray-400 mt-0.5">Unmatched</p>
                </div>
              </div>

              {/* Auto-match all button */}
              <button
                onClick={() => autoMatchMutation.mutate()}
                disabled={autoMatchMutation.isPending}
                className="shrink-0 flex items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                <Zap className="w-4 h-4 text-yellow-500" />
                {autoMatchMutation.isPending ? 'Running…' : 'Auto-match All'}
              </button>
            </div>
          </CardContent>
        </Card>

        {/* Preview prompt */}
        {previewResults.length === 0 && !isPreviewing && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg font-medium text-gray-600 mb-2">No results loaded yet</p>
            <p className="text-sm mb-4">
              Select a system above and click <strong>Preview Matches</strong> to load items for review.
            </p>
            <Button onClick={handlePreview} variant="outline">
              Preview {activeSystem} Matches
            </Button>
          </div>
        )}

        {isPreviewing && (
          <div className="text-center py-16">
            <PageSpinner />
            <p className="text-sm text-gray-400 mt-3">Running matching pipeline…</p>
          </div>
        )}

        {/* Three-column kanban */}
        {previewResults.length > 0 && (
          <div className="grid grid-cols-3 gap-5">
            {/* Column 1: Needs Review */}
            <div className="flex flex-col">
              <ColumnHeader
                label="Needs Review"
                count={needsReview.length}
                color="#D97706"
                icon={<AlertCircle className="w-4 h-4" />}
              />
              <div
                className="flex-1 border border-yellow-100 border-t-0 rounded-b-xl p-3 space-y-3 overflow-y-auto"
                style={{ maxHeight: '70vh', backgroundColor: '#FFFBF0' }}
              >
                {needsReview.length === 0 ? (
                  <p className="text-center text-xs text-gray-400 py-8">All clear ✓</p>
                ) : (
                  needsReview.map(item => (
                    <ReviewCard
                      key={item.source_id}
                      item={item}
                      onConfirm={handleConfirm}
                      onRtb={handleRtb}
                      onDismiss={handleDismiss}
                    />
                  ))
                )}
              </div>
            </div>

            {/* Column 2: Auto-Matched */}
            <div className="flex flex-col">
              <ColumnHeader
                label="Auto-Matched"
                count={autoMatched.length}
                color="#4A7C59"
                icon={<CheckCircle className="w-4 h-4" />}
              />
              <div
                className="flex-1 border border-green-100 border-t-0 rounded-b-xl p-3 space-y-3 overflow-y-auto"
                style={{ maxHeight: '70vh', backgroundColor: '#F0FFF4' }}
              >
                {autoMatched.length === 0 ? (
                  <p className="text-center text-xs text-gray-400 py-8">
                    Run auto-match to fill this column
                  </p>
                ) : (
                  autoMatched.map(item => (
                    <AutoMatchedCard
                      key={item.source_id}
                      item={item}
                      onUndo={handleUndo}
                    />
                  ))
                )}
              </div>
            </div>

            {/* Column 3: Unmatched */}
            <div className="flex flex-col">
              <ColumnHeader
                label="Unmatched"
                count={unmatched.length}
                color="#DC2626"
                icon={<XCircle className="w-4 h-4" />}
              />
              <div
                className="flex-1 border border-red-100 border-t-0 rounded-b-xl p-3 space-y-3 overflow-y-auto"
                style={{ maxHeight: '70vh', backgroundColor: '#FFF5F5' }}
              >
                {unmatched.length === 0 ? (
                  <p className="text-center text-xs text-gray-400 py-8">No unmatched items</p>
                ) : (
                  unmatched.map(item => (
                    <UnmatchedCard
                      key={item.source_id}
                      item={item}
                      onRtb={handleRtb}
                      onDismiss={handleDismiss}
                    />
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* Bottom stats */}
        {previewResults.length > 0 && (
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">
                    After resolving these{' '}
                    <strong>{needsReview.length + unmatched.length}</strong> items,
                    your Data Quality Score will be approximately{' '}
                    <strong style={{ color: '#4A7C59' }}>{Math.round(futureScore)}%</strong>
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-400">
                    Current:{' '}
                    <strong>{stats?.quality_score?.toFixed(0) ?? 0}%</strong> →{' '}
                    <strong style={{ color: '#4A7C59' }}>{Math.round(futureScore)}%</strong>
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
