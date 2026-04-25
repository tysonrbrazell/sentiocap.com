'use client'

import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { TrendingUp, AlertTriangle, RefreshCw, Calendar } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { formatCurrency } from '@/lib/utils'
import { Markdown } from '@/components/agents/Markdown'
import type { AgentReforecast } from '@/lib/types'

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OraclePage() {
  const [period, setPeriod] = useState(() => {
    const d = new Date()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    return `${d.getFullYear()}-${m}`
  })
  const [reforecast, setReforecast] = useState<AgentReforecast | null>(null)
  const [showNarrative, setShowNarrative] = useState(false)

  const mutation = useMutation({
    mutationFn: () => api.agent.reforecast(period),
    onSuccess: (data) => setReforecast(data),
  })

  // Build chart data from monthly forecast
  const chartData = reforecast?.monthly_forecast?.map((m) => ({
    month: m.period,
    Projected: m.projected_amount / 1_000_000,
  })) ?? []

  const riskFlags = reforecast?.risk_flags ?? []

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">📈</div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📈 Oracle</h1>
            <p className="text-sm text-gray-400 mt-1">
              Forecasting Agent · Forward-looking, probabilistic, honest about uncertainty
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg overflow-hidden bg-white">
              <Calendar className="w-4 h-4 text-gray-400 ml-3" />
              <input
                type="text"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                placeholder="YYYY-MM"
                className="border-0 px-2 py-2 text-sm focus:outline-none w-28"
              />
            </div>
            <Button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${mutation.isPending ? 'animate-spin' : ''}`} />
              {mutation.isPending ? 'Forecasting…' : 'Run Reforecast'}
            </Button>
          </div>
        </div>

        {/* Error */}
        {mutation.isError && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
            {(mutation.error as Error).message}
          </div>
        )}

        {/* Empty state */}
        {!reforecast && !mutation.isPending && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
              <span className="text-6xl">📈</span>
              <div className="text-center">
                <h3 className="text-base font-medium text-gray-700 mb-1">No forecast yet</h3>
                <p className="text-sm text-gray-400">
                  Select a period above and click <strong>Run Reforecast</strong> to generate a full-year projection.
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {mutation.isPending && (
          <Card>
            <CardContent className="flex items-center justify-center gap-3 py-16">
              <RefreshCw className="w-5 h-5 text-brand-accent animate-spin" />
              <span className="text-sm text-gray-500">Generating full-year reforecast…</span>
            </CardContent>
          </Card>
        )}

        {reforecast && !mutation.isPending && (
          <>
            {/* Projection card */}
            <div className="grid grid-cols-3 gap-4">
              <Card className="p-5">
                <p className="text-xs text-gray-500 mb-1">Annual Plan</p>
                <p className="text-2xl font-bold text-gray-900">{formatCurrency(reforecast.annual_plan)}</p>
              </Card>
              <Card className="p-5">
                <p className="text-xs text-gray-500 mb-1">Full-Year Forecast</p>
                <p className="text-2xl font-bold text-brand-accent">{formatCurrency(reforecast.full_year_forecast)}</p>
              </Card>
              <Card className={`p-5 ${Math.abs(reforecast.variance_vs_plan.pct) > 5 ? 'bg-yellow-50 border-yellow-200' : ''}`}>
                <p className="text-xs text-gray-500 mb-1">Variance vs Plan</p>
                <p className={`text-2xl font-bold ${reforecast.variance_vs_plan.direction === 'over' ? 'text-red-600' : 'text-green-600'}`}>
                  {reforecast.variance_vs_plan.direction === 'over' ? '+' : ''}
                  {reforecast.variance_vs_plan.pct.toFixed(1)}%
                </p>
                <p className="text-xs text-gray-400">{formatCurrency(Math.abs(reforecast.variance_vs_plan.amount))} {reforecast.variance_vs_plan.direction}</p>
              </Card>
            </div>

            {/* Monthly actuals vs projection chart */}
            {chartData.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="w-4 h-4 text-brand-accent" />
                    Monthly Projection — Full Year
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={chartData} margin={{ left: 10, right: 20 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                        <XAxis dataKey="month" tick={{ fontSize: 11, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                        <YAxis tickFormatter={(v) => `$${v}M`} tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                        <Tooltip formatter={(v: number) => [`$${v.toFixed(1)}M`]} />
                        <Legend />
                        <Line
                          type="monotone"
                          dataKey="Projected"
                          stroke="#4A7C59"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                          activeDot={{ r: 5 }}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Early warnings */}
            {riskFlags.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2 text-base text-yellow-700">
                    <AlertTriangle className="w-4 h-4" />
                    Early Warnings ({riskFlags.length})
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {riskFlags.map((flag, i) => (
                    <div key={i} className="flex items-start gap-2.5 px-3 py-2.5 bg-yellow-50 rounded-lg border border-yellow-100">
                      <AlertTriangle className="w-4 h-4 text-yellow-600 shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-700">{flag}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            )}

            {/* Variance explanation */}
            {reforecast.variance_explanation && (
              <Card>
                <CardHeader>
                  <button
                    className="flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900 w-full text-left transition-colors"
                    onClick={() => setShowNarrative(!showNarrative)}
                  >
                    {showNarrative ? '▲' : '▼'} Variance Explanation
                  </button>
                </CardHeader>
                {showNarrative && (
                  <CardContent>
                    <div className="bg-gray-50 rounded-xl p-5 border border-gray-100">
                      <Markdown content={reforecast.variance_explanation} />
                    </div>
                  </CardContent>
                )}
              </Card>
            )}
          </>
        )}
      </div>
    </div>
  )
}
