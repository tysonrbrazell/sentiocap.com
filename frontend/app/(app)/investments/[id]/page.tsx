'use client'

import { useParams } from 'next/navigation'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
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
import { ChevronLeft } from 'lucide-react'
import { api } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge, SignalDot } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { INVESTMENT_STATUS_LABELS, INVESTMENT_STATUS_COLORS, L2_LABELS } from '@/lib/constants'
import type { L2Category } from '@/lib/types'

export default function InvestmentDetailPage() {
  const { id } = useParams<{ id: string }>()

  const { data: inv, isLoading } = useQuery({
    queryKey: ['investment', id],
    queryFn: () => api.investments.get(id),
  })

  if (isLoading) return <PageSpinner />
  if (!inv) return null

  const planned = inv.planned_total ?? 0
  const actual = inv.actual_total
  const deployPct = planned > 0 ? (actual / planned) * 100 : 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <Link href="/investments" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-primary mb-3">
          <ChevronLeft className="w-4 h-4" />
          Investments
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-xl font-semibold text-brand-primary">{inv.name}</h1>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${INVESTMENT_STATUS_COLORS[inv.status] || 'bg-gray-100 text-gray-700'}`}>
                {INVESTMENT_STATUS_LABELS[inv.status] || inv.status}
              </span>
              {inv.l2_category && (
                <Badge variant={inv.l2_category.startsWith('RTB') ? 'rtb' : 'ctb'}>
                  {L2_LABELS[inv.l2_category as L2Category] || inv.l2_category}
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-4 mt-1 text-sm text-gray-500">
              {inv.owner && <span>Owner: <span className="font-medium text-brand-primary">{inv.owner}</span></span>}
              {inv.start_date && <span>Started: {inv.start_date}</span>}
              {inv.target_completion && <span>Target: {inv.target_completion}</span>}
            </div>
          </div>
          {inv.roi?.signal && (
            <div className="flex items-center gap-2">
              <SignalDot signal={inv.roi.signal} />
              <span className="text-sm text-gray-500">{inv.roi.signal}</span>
            </div>
          )}
        </div>
      </div>

      {/* Top KPI row */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Spend</p>
          <p className="text-2xl font-semibold text-brand-primary">
            {formatCurrency(actual, 'USD', true)}
          </p>
          <div className="mt-2">
            <div className="flex justify-between text-xs text-gray-400 mb-1">
              <span>of {formatCurrency(planned, 'USD', true)} planned</span>
              <span>{formatPercent(deployPct, 0)}</span>
            </div>
            <div className="w-full bg-gray-100 rounded-full h-1.5">
              <div
                className="bg-brand-accent h-1.5 rounded-full"
                style={{ width: `${Math.min(deployPct, 100)}%` }}
              />
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">ROI</p>
          <p className="text-2xl font-semibold text-brand-primary">
            {inv.roi?.current_roi != null ? formatPercent(inv.roi.current_roi) : '—'}
          </p>
          {inv.roi?.planned_roi != null && (
            <p className="text-xs text-gray-400 mt-1">
              Planned: {formatPercent(inv.roi.planned_roi)}
            </p>
          )}
          {inv.roi?.payback_months != null && (
            <p className="text-xs text-gray-400">
              Payback: {inv.roi.payback_months} months
            </p>
          )}
        </Card>

        <Card className="p-5">
          <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Benefits</p>
          <p className="text-2xl font-semibold text-brand-primary">{inv.benefit_count}</p>
          {inv.benefits_realized_pct != null && (
            <p className="text-xs text-gray-400 mt-1">
              {formatPercent(inv.benefits_realized_pct)} realized
            </p>
          )}
          {inv.roi?.composite_score != null && (
            <p className="text-xs text-gray-500 mt-1">
              Composite score: <span className="font-medium">{inv.roi.composite_score}/100</span>
            </p>
          )}
        </Card>
      </div>

      {/* Spend Tracking Chart */}
      {inv.spend_monthly.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Spend Tracking — Planned vs Actual</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={inv.spend_monthly} margin={{ left: 10, right: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                  <XAxis
                    dataKey="month"
                    tick={{ fontSize: 11, fill: '#9CA3AF' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tickFormatter={(v) => formatCurrency(v, 'USD', true)}
                    tick={{ fontSize: 11, fill: '#9CA3AF' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip formatter={(v: number) => formatCurrency(v)} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="planned"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    dot={false}
                    name="Planned"
                  />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="#22C55E"
                    strokeWidth={2}
                    dot={{ r: 3, fill: '#22C55E' }}
                    name="Actual"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Benefits */}
      {inv.benefits.length > 0 && (
        <div>
          <h2 className="text-base font-semibold text-brand-primary mb-3">Benefits</h2>
          <div className="grid grid-cols-2 gap-4">
            {inv.benefits.map((benefit) => {
              const target = benefit.target_value ?? 0
              const actual = benefit.actual_value ?? 0
              const pct = target > 0 ? (actual / target) * 100 : 0
              return (
                <Card key={benefit.id} className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <Badge variant="outline" className="mb-1">{benefit.benefit_type}</Badge>
                      <p className="text-sm text-gray-600">{benefit.description}</p>
                    </div>
                    <Badge variant={benefit.confidence === 'high' ? 'emerald' : benefit.confidence === 'medium' ? 'blue' : 'gray'}>
                      {benefit.confidence}
                    </Badge>
                  </div>
                  {target > 0 && (
                    <div className="mt-3">
                      <div className="flex justify-between text-xs text-gray-500 mb-1">
                        <span>Progress</span>
                        <span>{formatCurrency(actual, 'USD', true)} / {formatCurrency(target, 'USD', true)}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-1.5">
                        <div
                          className="bg-brand-accent h-1.5 rounded-full"
                          style={{ width: `${Math.min(pct, 100)}%` }}
                        />
                      </div>
                    </div>
                  )}
                  {benefit.formula && (
                    <p className="mt-2 text-xs text-gray-400 font-mono bg-gray-50 px-2 py-1 rounded">
                      {benefit.formula}
                    </p>
                  )}
                </Card>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
