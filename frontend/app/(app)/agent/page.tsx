'use client'

import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import {
  RefreshCw,
  Send,
  Zap,
  TrendingUp,
  FileText,
  BarChart2,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  Info,
  ArrowUpRight,
  ArrowDownRight,
  Bot,
} from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { formatCurrency } from '@/lib/utils'
import type { AgentBriefing, AgentAnswer, AgentMetric } from '@/lib/types'

// ---------------------------------------------------------------------------
// Markdown renderer (lightweight)
// ---------------------------------------------------------------------------
function Markdown({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <div className="prose prose-sm max-w-none text-gray-700 space-y-2">
      {lines.map((line, i) => {
        if (line.startsWith('## ')) {
          return <h2 key={i} className="text-base font-semibold text-gray-900 mt-4 mb-1">{line.slice(3)}</h2>
        }
        if (line.startsWith('### ')) {
          return <h3 key={i} className="text-sm font-semibold text-gray-800 mt-3 mb-1">{line.slice(4)}</h3>
        }
        if (line.startsWith('**') && line.endsWith('**')) {
          return <p key={i} className="font-semibold text-gray-800">{line.slice(2, -2)}</p>
        }
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span className="text-gray-400 mt-0.5">•</span>
              <span dangerouslySetInnerHTML={{ __html: boldInline(line.slice(2)) }} />
            </div>
          )
        }
        if (line.trim() === '') return <div key={i} className="h-1" />
        return (
          <p key={i} dangerouslySetInnerHTML={{ __html: boldInline(line) }} />
        )
      })}
    </div>
  )
}

function boldInline(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

// ---------------------------------------------------------------------------
// Metric chip
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
  const cls = colorMap[metric.type] || colorMap.info
  return (
    <div className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-xs font-medium ${cls}`}>
      {iconMap[metric.type]}
      <span className="text-gray-500">{metric.label}:</span>
      <span className="font-semibold">{metric.value}</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Today's Briefing section
// ---------------------------------------------------------------------------
function BriefingSection() {
  const [expanded, setExpanded] = useState(false)
  const {
    data: briefing,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['agent-briefing'],
    queryFn: () => api.agent.briefing(),
    staleTime: 1000 * 60 * 5, // 5 min cache
  })

  if (isLoading) {
    return (
      <Card className="p-8 flex items-center justify-center gap-3">
        <Bot className="w-5 h-5 text-brand-accent animate-pulse" />
        <span className="text-sm text-gray-500">Generating your morning briefing...</span>
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
              <span className="text-xs font-medium text-brand-accent uppercase tracking-wide">Today's Briefing</span>
            </div>
            <h2 className="text-xl font-semibold text-gray-900 leading-snug">
              {briefing?.headline || 'Loading briefing...'}
            </h2>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 shrink-0"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isFetching ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </CardHeader>

      <CardContent className="p-5 space-y-5">
        {/* Metrics row */}
        {briefing?.metrics_changed && briefing.metrics_changed.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {briefing.metrics_changed.map((m, i) => (
              <MetricChip key={i} metric={m} />
            ))}
          </div>
        )}

        {/* Action items */}
        {briefing?.recommended_actions && briefing.recommended_actions.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Recommended Actions
            </h3>
            <div className="space-y-1.5">
              {briefing.recommended_actions.map((action, i) => (
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

        {/* Upcoming deadlines */}
        {briefing?.upcoming && briefing.upcoming.length > 0 && (
          <div>
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Due Within 7 Days
            </h3>
            <div className="flex flex-wrap gap-2">
              {briefing.upcoming.map((item) => (
                <div key={item.id} className="flex items-center gap-1.5 px-2.5 py-1.5 bg-blue-50 border border-blue-100 rounded-lg text-xs text-blue-700">
                  <span className="font-medium">{item.name}</span>
                  <span className="text-blue-400">·</span>
                  <span>{item.target_completion}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Narrative — expandable */}
        {briefing?.narrative && (
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
                <Markdown content={briefing.narrative} />
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Chat history item
// ---------------------------------------------------------------------------
interface ChatItem {
  question: string
  answer: AgentAnswer
}

// ---------------------------------------------------------------------------
// Ask Your Agent section
// ---------------------------------------------------------------------------
function AskSection() {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<ChatItem[]>([])

  const mutation = useMutation({
    mutationFn: (q: string) => api.agent.ask(q),
    onSuccess: (data, q) => {
      setHistory((prev) => [{ question: q, answer: data }, ...prev].slice(0, 5))
      setQuestion('')
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || mutation.isPending) return
    mutation.mutate(question.trim())
  }

  function handleFollowUp(q: string) {
    setQuestion(q)
    mutation.mutate(q)
  }

  const confidenceColor = {
    high: 'text-green-600 bg-green-50 border-green-200',
    medium: 'text-amber-600 bg-amber-50 border-amber-200',
    low: 'text-red-600 bg-red-50 border-red-200',
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-gray-100">
        <CardTitle className="flex items-center gap-2 text-base">
          <Send className="w-4 h-4 text-brand-accent" />
          Ask Your Agent
        </CardTitle>
        <p className="text-xs text-gray-400 mt-0.5">
          Ask anything about your capital allocation
        </p>
      </CardHeader>

      <CardContent className="p-5 space-y-4">
        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="e.g. Why is CTB-GRW underspent? What's happening with Project X?"
            className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent placeholder:text-gray-400"
            disabled={mutation.isPending}
          />
          <Button
            type="submit"
            disabled={!question.trim() || mutation.isPending}
            className="px-4 py-2.5 flex items-center gap-1.5"
          >
            {mutation.isPending ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
            Ask
          </Button>
        </form>

        {/* Loading state */}
        {mutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-3">
            <Bot className="w-4 h-4 animate-pulse text-brand-accent" />
            Thinking...
          </div>
        )}

        {/* Error */}
        {mutation.isError && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
            {(mutation.error as Error).message}
          </div>
        )}

        {/* Chat history */}
        {history.length > 0 && (
          <div className="space-y-4">
            {history.map((item, i) => (
              <div key={i} className="rounded-xl border border-gray-100 overflow-hidden">
                {/* Question */}
                <div className="bg-gray-50 px-4 py-3 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-800">Q: {item.question}</p>
                </div>

                {/* Answer */}
                <div className="p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded border ${confidenceColor[item.answer.confidence]}`}>
                      {item.answer.confidence} confidence
                    </span>
                  </div>

                  <Markdown content={item.answer.answer} />

                  {/* Supporting data */}
                  {item.answer.supporting_data.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {item.answer.supporting_data.map((d, j) => (
                        <span key={j} className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-100">
                          {d}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Follow-up chips */}
                  {item.answer.follow_up_questions.length > 0 && (
                    <div className="pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-400 mb-2">Ask next:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {item.answer.follow_up_questions.map((q, j) => (
                          <button
                            key={j}
                            onClick={() => handleFollowUp(q)}
                            className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-brand-accent hover:text-brand-accent transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Scenario builder modal
// ---------------------------------------------------------------------------
function ScenarioModal({ onClose }: { onClose: () => void }) {
  const [action, setAction] = useState<'kill' | 'reallocate' | 'accelerate' | 'pause'>('reallocate')
  const [fromL2, setFromL2] = useState('CTB-EFF')
  const [toL2, setToL2] = useState('CTB-GRW')
  const [amount, setAmount] = useState('')
  const [result, setResult] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () =>
      api.agent.simulate([
        action === 'reallocate'
          ? { action, from_l2: fromL2, to_l2: toL2, amount: Number(amount) || 0 }
          : { action },
      ]),
    onSuccess: (data) => setResult(data.narrative),
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        <div className="p-5 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Run Scenario</h2>
          <p className="text-xs text-gray-400 mt-0.5">Model what-if changes to your portfolio</p>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 mb-1 block">Action</label>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value as typeof action)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            >
              <option value="reallocate">Reallocate funds between L2 categories</option>
              <option value="kill">Kill an investment</option>
              <option value="accelerate">Accelerate an investment</option>
              <option value="pause">Pause an investment</option>
            </select>
          </div>
          {action === 'reallocate' && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">From L2</label>
                  <input value={fromL2} onChange={(e) => setFromL2(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="text-xs font-medium text-gray-500 mb-1 block">To L2</label>
                  <input value={toL2} onChange={(e) => setToL2(e.target.value)}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1 block">Amount ($)</label>
                <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)}
                  placeholder="e.g. 5000000"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" />
              </div>
            </>
          )}
          {result && (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 max-h-48 overflow-y-auto">
              <Markdown content={result} />
            </div>
          )}
        </div>
        <div className="p-5 border-t border-gray-100 flex gap-2 justify-end">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? 'Modeling...' : 'Run Scenario'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reforecast modal
// ---------------------------------------------------------------------------
function ReforecastModal({ onClose }: { onClose: () => void }) {
  const [period, setPeriod] = useState(() => {
    const d = new Date()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    return `${d.getFullYear()}-${m}`
  })
  const [result, setResult] = useState<string | null>(null)

  const mutation = useMutation({
    mutationFn: () => api.agent.reforecast(period),
    onSuccess: (data) => setResult(data.variance_explanation),
  })

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
        <div className="p-5 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Auto-Reforecast</h2>
          <p className="text-xs text-gray-400 mt-0.5">Generate full-year reforecast from month-close actuals</p>
        </div>
        <div className="p-5 space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-500 mb-1 block">Through Period (YYYY-MM)</label>
            <input
              type="text"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
              placeholder="e.g. 2025-06"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          </div>
          {result && (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 max-h-48 overflow-y-auto">
              <Markdown content={result} />
            </div>
          )}
        </div>
        <div className="p-5 border-t border-gray-100 flex gap-2 justify-end">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending ? 'Generating...' : 'Reforecast'}
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Quick actions section
// ---------------------------------------------------------------------------
function QuickActionsSection() {
  const [showScenario, setShowScenario] = useState(false)
  const [showReforecast, setShowReforecast] = useState(false)
  const [boardDeck, setBoardDeck] = useState<string | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanResult, setScanResult] = useState<string | null>(null)

  const deckMutation = useMutation({
    mutationFn: () => {
      const q = new Date().getFullYear()
      const m = Math.ceil((new Date().getMonth() + 1) / 3)
      return api.agent.boardDeck(`Q${m}-${q}`)
    },
    onSuccess: (data) => setBoardDeck(data.content),
  })

  async function handleFullScan() {
    setScanning(true)
    setScanResult(null)
    try {
      const result = await api.decisions.scan()
      setScanResult(`Scan complete: ${result.new_decisions} new signal${result.new_decisions !== 1 ? 's' : ''} detected.`)
    } catch (e) {
      setScanResult('Scan failed. Try again.')
    } finally {
      setScanning(false)
    }
  }

  function downloadDeck() {
    if (!boardDeck) return
    const blob = new Blob([boardDeck], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `board-deck-${new Date().toISOString().slice(0, 7)}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <>
      <Card className="overflow-hidden">
        <CardHeader className="border-b border-gray-100">
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="w-4 h-4 text-brand-accent" />
            Quick Actions
          </CardTitle>
        </CardHeader>
        <CardContent className="p-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {/* Board Deck */}
            <button
              onClick={() => deckMutation.mutate()}
              disabled={deckMutation.isPending}
              className="flex flex-col items-center gap-2 p-4 bg-slate-50 hover:bg-slate-100 border border-slate-200 rounded-xl transition-colors text-center disabled:opacity-60"
            >
              <FileText className="w-5 h-5 text-slate-600" />
              <span className="text-xs font-medium text-slate-700">
                {deckMutation.isPending ? 'Generating...' : 'Board Deck'}
              </span>
            </button>

            {/* Scenario */}
            <button
              onClick={() => setShowScenario(true)}
              className="flex flex-col items-center gap-2 p-4 bg-purple-50 hover:bg-purple-100 border border-purple-200 rounded-xl transition-colors text-center"
            >
              <BarChart2 className="w-5 h-5 text-purple-600" />
              <span className="text-xs font-medium text-purple-700">Run Scenario</span>
            </button>

            {/* Reforecast */}
            <button
              onClick={() => setShowReforecast(true)}
              className="flex flex-col items-center gap-2 p-4 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-xl transition-colors text-center"
            >
              <TrendingUp className="w-5 h-5 text-blue-600" />
              <span className="text-xs font-medium text-blue-700">Reforecast</span>
            </button>

            {/* Full Scan */}
            <button
              onClick={handleFullScan}
              disabled={scanning}
              className="flex flex-col items-center gap-2 p-4 bg-green-50 hover:bg-green-100 border border-green-200 rounded-xl transition-colors text-center disabled:opacity-60"
            >
              <RefreshCw className={`w-5 h-5 text-green-600 ${scanning ? 'animate-spin' : ''}`} />
              <span className="text-xs font-medium text-green-700">
                {scanning ? 'Scanning...' : 'Full Scan'}
              </span>
            </button>
          </div>

          {/* Scan result */}
          {scanResult && (
            <div className="mt-3 text-sm text-green-700 bg-green-50 px-4 py-2.5 rounded-lg border border-green-200">
              {scanResult}
            </div>
          )}

          {/* Board deck preview */}
          {boardDeck && (
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-gray-500">Board deck generated</span>
                <button
                  onClick={downloadDeck}
                  className="text-xs text-brand-accent hover:underline font-medium"
                >
                  Download .md
                </button>
              </div>
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 max-h-64 overflow-y-auto">
                <Markdown content={boardDeck.slice(0, 1000) + (boardDeck.length > 1000 ? '\n\n*...truncated. Download for full deck.*' : '')} />
              </div>
            </div>
          )}

          {deckMutation.isError && (
            <div className="mt-3 text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
              {(deckMutation.error as Error).message}
            </div>
          )}
        </CardContent>
      </Card>

      {showScenario && <ScenarioModal onClose={() => setShowScenario(false)} />}
      {showReforecast && <ReforecastModal onClose={() => setShowReforecast(false)} />}
    </>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export default function AgentPage() {
  const { data: status } = useQuery({
    queryKey: ['agent-status'],
    queryFn: () => api.agent.status(),
    staleTime: 1000 * 30,
  })

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#FAFAF8' }}>
      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Page header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
              <Bot className="w-6 h-6 text-brand-accent" />
              SentioCap Agent
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Your autonomous capital intelligence advisor
            </p>
          </div>
          {status && (
            <div className="flex items-center gap-3 text-xs text-gray-400">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                <span className="font-medium text-green-600">Active</span>
              </div>
              <span>·</span>
              <span>{status.monitoring.investments_tracked} investments</span>
              <span>·</span>
              <span>{status.monitoring.pending_signals} pending signals</span>
            </div>
          )}
        </div>

        {/* Briefing */}
        <BriefingSection />

        {/* Ask */}
        <AskSection />

        {/* Quick actions */}
        <QuickActionsSection />
      </div>
    </div>
  )
}
