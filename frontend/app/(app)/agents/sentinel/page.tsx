'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  Info,
  Clock,
  RefreshCw,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import type { Decision, DecisionSummary, DecisionScanResult } from '@/lib/types'

// ---------------------------------------------------------------------------
// Severity config
// ---------------------------------------------------------------------------

const SEVERITY_CONFIG = {
  critical: {
    dot: 'bg-red-500',
    badge: 'bg-red-100 text-red-800 border border-red-200',
    icon: <AlertTriangle className="w-3.5 h-3.5" />,
    label: 'Critical',
  },
  warning: {
    dot: 'bg-yellow-500',
    badge: 'bg-yellow-100 text-yellow-800 border border-yellow-200',
    icon: <Clock className="w-3.5 h-3.5" />,
    label: 'Warning',
  },
  info: {
    dot: 'bg-blue-500',
    badge: 'bg-blue-100 text-blue-800 border border-blue-200',
    icon: <Info className="w-3.5 h-3.5" />,
    label: 'Info',
  },
} as const

// ---------------------------------------------------------------------------
// Decision Card
// ---------------------------------------------------------------------------

function DecisionCard({
  decision,
  onUpdate,
}: {
  decision: Decision
  onUpdate: (id: string, payload: { status?: string; resolution_notes?: string }) => void
}) {
  const [resolving, setResolving] = useState(false)
  const [notes, setNotes] = useState('')
  const cfg = SEVERITY_CONFIG[decision.severity as keyof typeof SEVERITY_CONFIG] ?? SEVERITY_CONFIG.info
  const isActive = !['resolved', 'dismissed'].includes(decision.status)

  return (
    <Card className="overflow-hidden">
      <div className="flex">
        <div className={`w-1 flex-shrink-0 ${cfg.dot}`} />
        <div className="flex-1 p-5">
          <div className="flex items-start justify-between gap-4 mb-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${cfg.badge}`}>
                {cfg.icon}
                {cfg.label}
              </span>
              <span className="text-xs text-gray-400 bg-gray-50 px-2 py-0.5 rounded font-mono">
                #{decision.category_number} · {decision.category.replace(/_/g, ' ')}
              </span>
              {decision.status !== 'new' && (
                <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  decision.status === 'resolved' ? 'bg-green-100 text-green-800' :
                  decision.status === 'dismissed' ? 'bg-gray-100 text-gray-500' :
                  'bg-blue-100 text-blue-800'
                }`}>
                  {decision.status.replace('_', ' ')}
                </span>
              )}
            </div>
            {decision.investment_name && (
              <span className="text-xs text-gray-500 whitespace-nowrap">📊 {decision.investment_name}</span>
            )}
          </div>

          <h3 className="text-sm font-semibold text-brand-primary mb-1.5 leading-snug">
            {decision.title}
          </h3>
          <p className="text-sm text-gray-600 mb-3 leading-relaxed">{decision.description}</p>

          <div className="bg-brand-accent-light border border-green-100 rounded-md px-3 py-2.5 mb-3">
            <p className="text-xs font-semibold text-brand-accent uppercase tracking-wide mb-0.5">
              Recommended Action
            </p>
            <p className="text-sm text-gray-700">{decision.recommended_action}</p>
          </div>

          <div className="flex items-center justify-between gap-4">
            <div>
              {decision.impact_estimate && (
                <p className="text-xs text-gray-500">
                  <span className="font-medium text-gray-700">Impact: </span>
                  {decision.impact_estimate}
                </p>
              )}
            </div>
            <p className="text-xs text-gray-400">{new Date(decision.created_at).toLocaleDateString()}</p>
          </div>

          {isActive && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100">
              {decision.status === 'new' && (
                <Button size="sm" variant="outline" onClick={() => onUpdate(decision.id, { status: 'acknowledged' })}>
                  <CheckCircle className="w-3.5 h-3.5 mr-1" /> Acknowledge
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={() => setResolving(!resolving)}>
                <CheckCircle className="w-3.5 h-3.5 mr-1" /> Resolve
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => onUpdate(decision.id, { status: 'dismissed' })}
                className="text-gray-400 hover:text-red-600"
              >
                <XCircle className="w-3.5 h-3.5 mr-1" /> Dismiss
              </Button>
            </div>
          )}

          {resolving && (
            <div className="mt-3 space-y-2">
              <textarea
                className="w-full border border-gray-200 rounded-md text-sm p-2.5 focus:outline-none focus:ring-2 focus:ring-brand-accent resize-none"
                rows={2}
                placeholder="Resolution notes (optional)…"
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    onUpdate(decision.id, { status: 'resolved', resolution_notes: notes || undefined })
                    setResolving(false)
                  }}
                >
                  Confirm Resolution
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setResolving(false)}>Cancel</Button>
              </div>
            </div>
          )}

          {decision.resolution_notes && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-xs text-gray-500 italic">{decision.resolution_notes}</p>
            </div>
          )}
        </div>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type FilterTab = 'all' | 'critical' | 'warning' | 'info' | 'resolved'

export default function SentinelPage() {
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [scanning, setScanning] = useState(false)
  const queryClient = useQueryClient()

  const { data: decisions = [], isLoading } = useQuery<Decision[]>({
    queryKey: ['decisions', activeTab],
    queryFn: () => {
      const params = new URLSearchParams()
      if (activeTab !== 'all' && activeTab !== 'resolved') params.set('severity', activeTab)
      if (activeTab === 'resolved') {
        params.set('status', 'resolved')
      } else {
        params.set('status', 'new,acknowledged,in_progress')
      }
      return api.decisions.list(params.toString())
    },
  })

  const { data: summary } = useQuery<DecisionSummary>({
    queryKey: ['decisions-summary'],
    queryFn: () => api.decisions.summary(),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: { status?: string; resolution_notes?: string } }) =>
      api.decisions.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
      queryClient.invalidateQueries({ queryKey: ['decisions-summary'] })
    },
  })

  async function handleScan() {
    setScanning(true)
    try {
      await api.decisions.scan()
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
      queryClient.invalidateQueries({ queryKey: ['decisions-summary'] })
    } finally {
      setScanning(false)
    }
  }

  const TABS: { key: FilterTab; label: string; emoji: string; count?: number }[] = [
    { key: 'all', label: 'All', emoji: '🎯', count: summary?.total },
    { key: 'critical', label: 'Critical', emoji: '🔴', count: summary?.by_severity?.critical },
    { key: 'warning', label: 'Warning', emoji: '🟡', count: summary?.by_severity?.warning },
    { key: 'info', label: 'Info', emoji: '🟢', count: summary?.by_severity?.info },
    { key: 'resolved', label: 'Resolved', emoji: '✅', count: summary?.by_status?.resolved },
  ]

  const filtered = decisions.filter((d) => {
    if (activeTab === 'resolved') return d.status === 'resolved'
    if (activeTab === 'all') return !['resolved', 'dismissed'].includes(d.status)
    return d.severity === activeTab && !['resolved', 'dismissed'].includes(d.status)
  })

  if (isLoading) return <PageSpinner />

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">🎯</div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">🎯 Sentinel</h1>
            <p className="text-sm text-gray-400 mt-1">Signal Detection Agent · Vigilant, pattern-matching, doesn't cry wolf</p>
          </div>
          <Button onClick={handleScan} disabled={scanning} variant="secondary" className="flex items-center gap-2">
            <RefreshCw className={`w-4 h-4 ${scanning ? 'animate-spin' : ''}`} />
            {scanning ? 'Scanning…' : 'Run Full Scan'}
          </Button>
        </div>

        {/* Summary bar */}
        {summary && (
          <div className="grid grid-cols-5 gap-3">
            <Card className="p-4 text-center">
              <p className="text-2xl font-bold text-red-600">{summary.by_severity?.critical ?? 0}</p>
              <p className="text-xs text-gray-500 mt-0.5">🔴 Critical</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-2xl font-bold text-yellow-600">{summary.by_severity?.warning ?? 0}</p>
              <p className="text-xs text-gray-500 mt-0.5">🟡 Warning</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-2xl font-bold text-blue-600">{summary.by_severity?.info ?? 0}</p>
              <p className="text-xs text-gray-500 mt-0.5">🟢 Info</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-2xl font-bold text-green-600">{summary.by_status?.resolved ?? 0}</p>
              <p className="text-xs text-gray-500 mt-0.5">✅ Resolved</p>
            </Card>
            <Card className="p-4 text-center">
              <p className="text-2xl font-bold text-brand-primary">{summary.active ?? 0}</p>
              <p className="text-xs text-gray-500 mt-0.5">⚡ Active</p>
            </Card>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-100">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-brand-accent text-brand-accent'
                  : 'border-transparent text-gray-500 hover:text-brand-primary'
              }`}
            >
              {tab.emoji} {tab.label}
              {tab.count != null && tab.count > 0 && (
                <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full font-medium ${
                  activeTab === tab.key ? 'bg-brand-accent text-white' : 'bg-gray-100 text-gray-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Decisions */}
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center">
            <span className="text-5xl mb-4">🎯</span>
            <h3 className="text-sm font-medium text-gray-500 mb-1">No signals in this category</h3>
            <p className="text-xs text-gray-400">Run a scan to detect new signals, or check another tab.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((d) => (
              <DecisionCard
                key={d.id}
                decision={d}
                onUpdate={(id, payload) => updateMutation.mutate({ id, payload })}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
