'use client'

import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Plus, Trash2, BarChart2 } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Markdown } from '@/components/agents/Markdown'
import type { ScenarioChange, AgentScenario, SavedScenario } from '@/lib/types'

// ---------------------------------------------------------------------------
// Scenario builder modal
// ---------------------------------------------------------------------------

interface ActionRow {
  action: 'kill' | 'accelerate' | 'reallocate' | 'pause'
  investment_id?: string
  from_l2?: string
  to_l2?: string
  amount?: number
}

function ScenarioModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient()
  const [rows, setRows] = useState<ActionRow[]>([{ action: 'reallocate', from_l2: 'CTB-EFF', to_l2: 'CTB-GRW' }])
  const [scenarioName, setScenarioName] = useState('')
  const [result, setResult] = useState<AgentScenario | null>(null)

  const simulateMutation = useMutation({
    mutationFn: () => api.agent.simulate(rows as ScenarioChange[]),
    onSuccess: (data) => setResult(data),
  })

  const saveMutation = useMutation({
    mutationFn: () => api.strategist.saveScenario(scenarioName || 'Untitled Scenario', rows as ScenarioChange[], result ?? undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategist-scenarios'] })
      onClose()
    },
  })

  function addRow() {
    setRows((prev) => [...prev, { action: 'reallocate', from_l2: 'CTB-EFF', to_l2: 'CTB-GRW' }])
  }

  function removeRow(i: number) {
    setRows((prev) => prev.filter((_, idx) => idx !== i))
  }

  function updateRow(i: number, patch: Partial<ActionRow>) {
    setRows((prev) => prev.map((r, idx) => idx === i ? { ...r, ...patch } : r))
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-5 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900 text-lg">New Scenario</h2>
          <p className="text-xs text-gray-400 mt-0.5">Model what-if changes to your portfolio</p>
        </div>

        <div className="p-5 space-y-4">
          {/* Scenario name */}
          <div>
            <label className="text-xs font-medium text-gray-500 mb-1 block">Scenario Name</label>
            <input
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              placeholder="e.g. Kill Project X and reallocate to CTB-GRW"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent"
            />
          </div>

          {/* Action rows */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-gray-500">Actions</label>
              <button onClick={addRow} className="text-xs text-brand-accent hover:underline flex items-center gap-1">
                <Plus className="w-3.5 h-3.5" /> Add action
              </button>
            </div>

            {rows.map((row, i) => (
              <div key={i} className="flex items-start gap-2 p-3 bg-gray-50 rounded-xl border border-gray-100">
                <div className="flex-1 grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-gray-500 mb-1 block">Action</label>
                    <select
                      value={row.action}
                      onChange={(e) => updateRow(i, { action: e.target.value as ActionRow['action'] })}
                      className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white"
                    >
                      <option value="kill">Kill</option>
                      <option value="accelerate">Accelerate</option>
                      <option value="reallocate">Reallocate</option>
                      <option value="pause">Pause</option>
                    </select>
                  </div>

                  {row.action === 'reallocate' && (
                    <>
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">From L2</label>
                        <input
                          value={row.from_l2 ?? ''}
                          onChange={(e) => updateRow(i, { from_l2: e.target.value })}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">To L2</label>
                        <input
                          value={row.to_l2 ?? ''}
                          onChange={(e) => updateRow(i, { to_l2: e.target.value })}
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                        />
                      </div>
                      <div>
                        <label className="text-xs text-gray-500 mb-1 block">Amount ($)</label>
                        <input
                          type="number"
                          value={row.amount ?? ''}
                          onChange={(e) => updateRow(i, { amount: Number(e.target.value) })}
                          placeholder="e.g. 5000000"
                          className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                        />
                      </div>
                    </>
                  )}

                  {(row.action === 'kill' || row.action === 'accelerate' || row.action === 'pause') && (
                    <div>
                      <label className="text-xs text-gray-500 mb-1 block">Investment ID (optional)</label>
                      <input
                        value={row.investment_id ?? ''}
                        onChange={(e) => updateRow(i, { investment_id: e.target.value })}
                        placeholder="Investment UUID"
                        className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                      />
                    </div>
                  )}
                </div>

                {rows.length > 1 && (
                  <button onClick={() => removeRow(i)} className="text-gray-400 hover:text-red-500 mt-5 transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>

          {/* Results */}
          {result && (
            <div className="bg-slate-50 rounded-xl p-4 border border-slate-100 space-y-3">
              <h3 className="text-sm font-semibold text-gray-800">Projected Impact</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-xs text-gray-500">CTB shift:</span>
                  <p className="font-medium text-gray-900">{result.projected_ctb_split.new_ctb_pct?.toFixed(1) ?? '—'}%</p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">ROI impact:</span>
                  <p className="font-medium text-gray-900">{result.projected_roi_impact}</p>
                </div>
                <div>
                  <span className="text-xs text-gray-500">Benchmark shift:</span>
                  <p className="font-medium text-gray-900">{result.benchmark_shift}</p>
                </div>
                {result.freed_resources.budget_freed && (
                  <div>
                    <span className="text-xs text-gray-500">Budget freed:</span>
                    <p className="font-medium text-green-700">${(result.freed_resources.budget_freed / 1_000_000).toFixed(1)}M</p>
                  </div>
                )}
              </div>
              {result.risks.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-red-600 mb-1">Risks:</p>
                  <ul className="space-y-1">
                    {result.risks.map((r, i) => (
                      <li key={i} className="text-xs text-gray-700 flex gap-1.5"><span>•</span>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="max-h-40 overflow-y-auto">
                <Markdown content={result.narrative} />
              </div>
            </div>
          )}
        </div>

        <div className="p-5 border-t border-gray-100 flex gap-2 justify-between">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              onClick={() => simulateMutation.mutate()}
              disabled={simulateMutation.isPending}
            >
              {simulateMutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin mr-1" /> : null}
              {simulateMutation.isPending ? 'Modeling…' : 'Run Scenario'}
            </Button>
            {result && (
              <Button onClick={() => saveMutation.mutate()} disabled={saveMutation.isPending}>
                {saveMutation.isPending ? 'Saving…' : 'Save Scenario'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function StrategistPage() {
  const [showModal, setShowModal] = useState(false)
  const [compareIds, setCompareIds] = useState<string[]>([])

  const { data: scenarios = [], isLoading } = useQuery<SavedScenario[]>({
    queryKey: ['strategist-scenarios'],
    queryFn: () => api.strategist.scenarios(),
    staleTime: 1000 * 60,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.strategist.deleteScenario(id),
  })

  function toggleCompare(id: string) {
    setCompareIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(-2)
    )
  }

  const compareScenarios = scenarios.filter((s) => compareIds.includes(s.id))

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">🔮</div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">🔮 Strategist</h1>
            <p className="text-sm text-gray-400 mt-1">
              Scenario Agent · Strategic, plays chess not checkers, shows trade-offs
            </p>
          </div>
          <Button onClick={() => setShowModal(true)} className="flex items-center gap-2">
            <Plus className="w-4 h-4" />
            New Scenario
          </Button>
        </div>

        {/* Compare panel */}
        {compareScenarios.length === 2 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Side-by-Side Comparison</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                {compareScenarios.map((s) => (
                  <div key={s.id} className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                    <h3 className="font-semibold text-gray-800 mb-3">{s.name}</h3>
                    {s.result && (
                      <div className="space-y-1.5 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-500">CTB after:</span>
                          <span className="font-medium">{s.result.projected_ctb_split.new_ctb_pct?.toFixed(1) ?? '—'}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">ROI impact:</span>
                          <span className="font-medium">{s.result.projected_roi_impact}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Benchmark:</span>
                          <span className="font-medium">{s.result.benchmark_shift}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Risks:</span>
                          <span className="font-medium text-red-600">{s.result.risks.length}</span>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Scenarios list */}
        {isLoading ? (
          <div className="text-center py-12 text-gray-400 text-sm">Loading scenarios…</div>
        ) : scenarios.length === 0 ? (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
              <span className="text-6xl">🔮</span>
              <div className="text-center">
                <h3 className="text-base font-medium text-gray-700 mb-1">No scenarios yet</h3>
                <p className="text-sm text-gray-400">Click <strong>New Scenario</strong> to model your first what-if.</p>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {scenarios.map((scenario) => (
              <Card key={scenario.id} className="overflow-hidden">
                <div className="p-5">
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <h3 className="font-semibold text-gray-900">{scenario.name}</h3>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {scenario.changes.length} action{scenario.changes.length !== 1 ? 's' : ''} ·{' '}
                        {new Date(scenario.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => toggleCompare(scenario.id)}
                        className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                          compareIds.includes(scenario.id)
                            ? 'bg-brand-accent-light border-brand-accent text-brand-accent'
                            : 'border-gray-200 text-gray-500 hover:border-brand-accent hover:text-brand-accent'
                        }`}
                      >
                        <BarChart2 className="w-3.5 h-3.5 inline mr-1" />
                        {compareIds.includes(scenario.id) ? 'Comparing' : 'Compare'}
                      </button>
                      <button
                        onClick={() => deleteMutation.mutate(scenario.id)}
                        className="text-gray-400 hover:text-red-500 p-1 transition-colors"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Action chips */}
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {scenario.changes.map((c, i) => (
                      <span key={i} className="text-xs px-2.5 py-1 bg-gray-100 text-gray-700 rounded-full border border-gray-200">
                        {c.action.toUpperCase()}
                        {c.from_l2 ? ` ${c.from_l2} → ${c.to_l2}` : ''}
                        {c.amount ? ` ($${(c.amount / 1_000_000).toFixed(1)}M)` : ''}
                      </span>
                    ))}
                  </div>

                  {/* Result summary */}
                  {scenario.result && (
                    <div className="bg-gray-50 rounded-lg p-3 border border-gray-100 grid grid-cols-3 gap-3 text-sm">
                      <div>
                        <span className="text-xs text-gray-500">CTB shift</span>
                        <p className="font-medium">{scenario.result.projected_ctb_split.new_ctb_pct?.toFixed(1) ?? '—'}%</p>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500">ROI impact</span>
                        <p className="font-medium">{scenario.result.projected_roi_impact}</p>
                      </div>
                      <div>
                        <span className="text-xs text-gray-500">Risks</span>
                        <p className={`font-medium ${scenario.result.risks.length > 0 ? 'text-yellow-600' : 'text-green-600'}`}>
                          {scenario.result.risks.length > 0 ? `${scenario.result.risks.length} identified` : 'None'}
                        </p>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      {showModal && <ScenarioModal onClose={() => setShowModal(false)} />}
    </div>
  )
}
