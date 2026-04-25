'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { Bot, RefreshCw, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, Info } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { getStoredUser } from '@/lib/utils'
import { Markdown } from '@/components/agents/Markdown'
import type { AgentMetric, AgentStatusLevel } from '@/lib/types'

// ---------------------------------------------------------------------------
// Agent roster (static config, status comes from API in production)
// ---------------------------------------------------------------------------

const AGENTS = [
  {
    id: 'scout',
    emoji: '🔍',
    name: 'Scout',
    description: 'Classifies every expense into the Investment Intent Taxonomy',
    href: '/agents/scout',
    defaultMetric: '— items classified',
    statusDefault: 'active' as AgentStatusLevel,
  },
  {
    id: 'sentinel',
    emoji: '🎯',
    name: 'Sentinel',
    description: 'Watches your portfolio and fires signals when action is needed',
    href: '/agents/sentinel',
    defaultMetric: '— active signals',
    statusDefault: 'needs_attention' as AgentStatusLevel,
  },
  {
    id: 'compass',
    emoji: '📊',
    name: 'Compass',
    description: 'Tracks your position vs sector peers and benchmarks',
    href: '/agents/compass',
    defaultMetric: '— categories benchmarked',
    statusDefault: 'active' as AgentStatusLevel,
  },
  {
    id: 'oracle',
    emoji: '📈',
    name: 'Oracle',
    description: 'Generates full-year reforecasts and early-warning alerts',
    href: '/agents/oracle',
    defaultMetric: '— month reforecast',
    statusDefault: 'active' as AgentStatusLevel,
  },
  {
    id: 'scribe',
    emoji: '📝',
    name: 'Scribe',
    description: 'Writes board decks, CFO briefings, and variance reports',
    href: '/agents/scribe',
    defaultMetric: '— reports generated',
    statusDefault: 'idle' as AgentStatusLevel,
  },
  {
    id: 'sage',
    emoji: '💬',
    name: 'Sage',
    description: 'Answers any question about your capital allocation instantly',
    href: '/agents/sage',
    defaultMetric: 'Ready to answer',
    statusDefault: 'active' as AgentStatusLevel,
  },
  {
    id: 'strategist',
    emoji: '🔮',
    name: 'Strategist',
    description: 'Models what-if scenarios so decisions are backed by data',
    href: '/agents/strategist',
    defaultMetric: '— scenarios saved',
    statusDefault: 'idle' as AgentStatusLevel,
  },
  {
    id: 'guardian',
    emoji: '🛡️',
    name: 'Guardian',
    description: 'Ensures every allocation follows policy — nothing falls through',
    href: '/agents/guardian',
    defaultMetric: '— compliance score',
    statusDefault: 'active' as AgentStatusLevel,
  },
]

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<AgentStatusLevel, { label: string; classes: string; dot: string }> = {
  active: {
    label: 'Active',
    classes: 'bg-green-50 text-green-700 border-green-200',
    dot: 'bg-green-400',
  },
  needs_attention: {
    label: 'Needs Attention',
    classes: 'bg-yellow-50 text-yellow-700 border-yellow-200',
    dot: 'bg-yellow-400',
  },
  idle: {
    label: 'Idle',
    classes: 'bg-gray-50 text-gray-500 border-gray-200',
    dot: 'bg-gray-300',
  },
}

function StatusBadge({ status }: { status: AgentStatusLevel }) {
  const cfg = STATUS_CONFIG[status]
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium border ${cfg.classes}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Agent Card
// ---------------------------------------------------------------------------

function AgentCard({
  agent,
  status,
  lastRun,
  metric,
}: {
  agent: typeof AGENTS[0]
  status: AgentStatusLevel
  lastRun?: string
  metric?: string
}) {
  const router = useRouter()

  return (
    <button
      onClick={() => router.push(agent.href)}
      className="text-left group bg-white rounded-2xl border border-gray-100 p-5 hover:border-brand-accent hover:shadow-md transition-all duration-200 flex flex-col gap-3"
    >
      {/* Top row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl">{agent.emoji}</span>
          <span className="text-base font-semibold text-gray-900 group-hover:text-brand-accent transition-colors">
            {agent.name}
          </span>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Description */}
      <p className="text-sm text-gray-500 leading-relaxed">{agent.description}</p>

      {/* Footer */}
      <div className="flex items-center justify-between mt-auto pt-2 border-t border-gray-50">
        <span className="text-xs font-medium text-brand-accent">{metric ?? agent.defaultMetric}</span>
        {lastRun && (
          <span className="text-xs text-gray-400">
            {new Date(lastRun).toLocaleDateString()}
          </span>
        )}
      </div>
    </button>
  )
}

// ---------------------------------------------------------------------------
// MetricChip
// ---------------------------------------------------------------------------

function MetricChip({ metric }: { metric: AgentMetric }) {
  const colorMap = {
    ok: 'bg-green-50 text-green-700 border-green-200',
    info: 'bg-blue-50 text-blue-700 border-blue-200',
    warning: 'bg-amber-50 text-amber-700 border-amber-200',
    critical: 'bg-red-50 text-red-700 border-red-200',
  }
  const iconMap = {
    ok: <CheckCircle className="w-3.5 h-3.5" />,
    info: <Info className="w-3.5 h-3.5" />,
    warning: <AlertTriangle className="w-3.5 h-3.5" />,
    critical: <AlertTriangle className="w-3.5 h-3.5" />,
  }
  return (
    <div className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium ${colorMap[metric.type]}`}>
      {iconMap[metric.type]}
      <span className="text-gray-500">{metric.label}:</span>
      <span className="font-semibold">{metric.value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Morning briefing
// ---------------------------------------------------------------------------

function MorningBriefing() {
  const [expanded, setExpanded] = useState(false)
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['agent-briefing'],
    queryFn: () => api.agent.briefing(),
    staleTime: 1000 * 60 * 5,
  })

  if (isLoading) {
    return (
      <Card className="p-8 flex items-center justify-center gap-3">
        <Bot className="w-5 h-5 text-brand-accent animate-pulse" />
        <span className="text-sm text-gray-500">Generating your morning briefing…</span>
      </Card>
    )
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="bg-gradient-to-r from-slate-50 to-white border-b border-gray-100">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <Bot className="w-4 h-4 text-brand-accent" />
              <span className="text-xs font-medium text-brand-accent uppercase tracking-wide">Morning Briefing</span>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 leading-snug">
              {data?.headline ?? 'No briefing available'}
            </h2>
          </div>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching} className="flex items-center gap-1.5 shrink-0">
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-5 space-y-5">
        {/* Metrics */}
        {data?.metrics_changed && data.metrics_changed.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {data.metrics_changed.map((m, i) => <MetricChip key={i} metric={m} />)}
          </div>
        )}

        {/* Action items */}
        {data?.recommended_actions && data.recommended_actions.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Action Items</h3>
            <div className="space-y-1.5">
              {data.recommended_actions.map((action, i) => (
                <div key={i} className="flex items-start gap-2.5 py-2 px-3 bg-amber-50 rounded-lg border border-amber-100">
                  <span className="w-5 h-5 rounded-full bg-amber-200 text-amber-800 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  <span className="text-sm text-gray-700">{action}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Upcoming */}
        {data?.upcoming && data.upcoming.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">Due Within 7 Days</h3>
            <div className="flex flex-wrap gap-2">
              {data.upcoming.map((item) => (
                <div key={item.id} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-700">
                  <span className="font-medium">{item.name}</span>
                  <span className="text-blue-400">·</span>
                  <span>{item.target_completion}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Narrative */}
        {data?.narrative && (
          <div className="border-t border-gray-100 pt-4">
            <button
              className="flex items-center gap-2 text-xs font-medium text-gray-500 hover:text-gray-700 mb-3 transition-colors"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
              {expanded ? 'Collapse narrative' : 'Read full narrative'}
            </button>
            {expanded && (
              <div className="bg-gray-50 rounded-xl p-5 border border-gray-100">
                <Markdown content={data.narrative} />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AgentsPage() {
  const user = getStoredUser()
  const { data: agentStatus } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => api.agent.status(),
    staleTime: 1000 * 30,
  })

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAFAF8' }}>
      <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Your Agent Team</h1>
            <p className="text-sm text-gray-400 mt-1">
              {agentStatus?.org_name ?? user?.name ?? 'Your organization'} · 8 agents always-on
            </p>
          </div>
          {agentStatus && (
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                <span className="font-medium text-green-600">All systems active</span>
              </div>
              <span>·</span>
              <span>{agentStatus.monitoring.investments_tracked} investments tracked</span>
            </div>
          )}
        </div>

        {/* Agent grid — 2x4 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {AGENTS.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              status={agent.statusDefault}
            />
          ))}
        </div>

        {/* Morning briefing */}
        <MorningBriefing />
      </div>
    </div>
  )
}
