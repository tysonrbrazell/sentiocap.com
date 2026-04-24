'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { Plus, TrendingUp } from 'lucide-react'
import { api } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge, SignalDot } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import { INVESTMENT_STATUS_LABELS, INVESTMENT_STATUS_COLORS, L2_LABELS } from '@/lib/constants'
import type { L2Category } from '@/lib/types'

export default function InvestmentsPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['investments'],
    queryFn: () => api.investments.list(),
  })

  if (isLoading) return <PageSpinner />

  const investments = data?.investments ?? []
  const summary = data?.portfolio_summary

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-brand-primary">Investments</h1>
          <p className="text-sm text-gray-500 mt-0.5">CTB investment portfolio</p>
        </div>
        <Link href="/investments/new">
          <Button>
            <Plus className="w-4 h-4" />
            New Investment
          </Button>
        </Link>
      </div>

      {/* Portfolio Summary */}
      {summary && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Total Planned</p>
            <p className="text-lg font-semibold text-brand-primary mt-1">
              {formatCurrency(summary.total_planned, 'USD', true)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Total Actual</p>
            <p className="text-lg font-semibold text-brand-primary mt-1">
              {formatCurrency(summary.total_actual, 'USD', true)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Deployment Rate</p>
            <p className="text-lg font-semibold text-emerald-600 mt-1">
              {formatPercent(summary.deployment_rate)}
            </p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Portfolio ROI</p>
            <p className="text-lg font-semibold text-brand-primary mt-1">
              {summary.portfolio_roi != null ? formatPercent(summary.portfolio_roi) : '—'}
            </p>
            {summary.at_risk_count > 0 && (
              <p className="text-xs text-red-500 mt-0.5">{summary.at_risk_count} at risk</p>
            )}
          </Card>
        </div>
      )}

      {/* Investment Grid */}
      {investments.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <TrendingUp className="w-12 h-12 text-gray-300 mb-4" />
          <h3 className="text-base font-medium text-gray-600 mb-1">No investments yet</h3>
          <p className="text-sm text-gray-400 mb-4">Track your CTB investments and ROI</p>
          <Link href="/investments/new">
            <Button>
              <Plus className="w-4 h-4" />
              Add first investment
            </Button>
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-3 gap-4">
          {investments.map((inv) => {
            const spent = inv.actual_total
            const planned = inv.planned_total ?? 0
            const pct = planned > 0 ? Math.min((spent / planned) * 100, 100) : 0
            return (
              <Link key={inv.id} href={`/investments/${inv.id}`}>
                <Card className="p-5 hover:shadow-card-hover transition-shadow cursor-pointer">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 min-w-0 mr-2">
                      <p className="text-sm font-semibold text-brand-primary truncate">{inv.name}</p>
                      {inv.l2_category && (
                        <Badge variant={inv.l2_category.startsWith('RTB') ? 'rtb' : 'ctb'} className="mt-1">
                          {L2_LABELS[inv.l2_category as L2Category] || inv.l2_category}
                        </Badge>
                      )}
                    </div>
                    {inv.roi?.signal && <SignalDot signal={inv.roi.signal} />}
                  </div>

                  <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                    <span>Deployed</span>
                    <span>{formatPercent(pct, 0)}</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div
                      className="bg-brand-accent h-1.5 rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <div className="mt-3 flex items-center justify-between">
                    <div className="text-xs text-gray-500">
                      {formatCurrency(spent, 'USD', true)} / {formatCurrency(planned, 'USD', true)}
                    </div>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${INVESTMENT_STATUS_COLORS[inv.status] || 'bg-gray-100 text-gray-700'}`}>
                      {INVESTMENT_STATUS_LABELS[inv.status] || inv.status}
                    </span>
                  </div>

                  {inv.roi?.current_roi != null && (
                    <div className="mt-2 pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-500">
                        ROI: <span className="font-medium text-brand-primary">{formatPercent(inv.roi.current_roi)}</span>
                      </p>
                    </div>
                  )}
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
