'use client'

import { useQuery } from '@tanstack/react-query'
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Treemap,
} from 'recharts'
import { api } from '@/lib/api'
import { formatCurrency, formatPercent } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge, SignalDot } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { L2_LABELS, L2_COLORS, PLAN_STATUS_COLORS } from '@/lib/constants'
import type { L2Category, VarianceSignal } from '@/lib/types'

// ---------------------------------------------------------------------------
// KPI Tile
// ---------------------------------------------------------------------------
function KpiTile({
  label,
  value,
  sub,
  signal,
}: {
  label: string
  value: string
  sub?: string
  signal?: VarianceSignal
}) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between mb-1">
        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{label}</p>
        {signal && <SignalDot signal={signal} />}
      </div>
      <p className="text-2xl font-semibold text-brand-primary mt-1">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Custom Treemap content
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTreemapContent(props: any) {
  const { x, y, width, height, name, value, color } = props
  if (width < 30 || height < 20) return null
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} fill={color || '#4A7C59'} rx={3} />
      <text
        x={x + width / 2}
        y={y + height / 2 - 6}
        textAnchor="middle"
        fill="#fff"
        fontSize={Math.min(12, width / 6)}
        fontWeight="500"
      >
        {name}
      </text>
      <text
        x={x + width / 2}
        y={y + height / 2 + 8}
        textAnchor="middle"
        fill="rgba(255,255,255,0.8)"
        fontSize={Math.min(10, width / 8)}
      >
        {formatCurrency(value, 'USD', true)}
      </text>
    </g>
  )
}

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------
export default function DashboardPage() {
  const { data: summary, isLoading: loadingSummary } = useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: () => api.dashboard.summary(),
  })

  const { data: treemapData } = useQuery({
    queryKey: ['dashboard', 'treemap'],
    queryFn: () => api.dashboard.treemap(),
  })

  const { data: varianceData } = useQuery({
    queryKey: ['dashboard', 'variance'],
    queryFn: () => api.dashboard.variance(),
  })

  if (loadingSummary) return <PageSpinner />

  // Prepare donut data
  const donutData = summary
    ? [
        { name: 'RTB', value: summary.rtb.total, color: '#3B82F6' },
        { name: 'CTB', value: summary.ctb.total, color: '#22C55E' },
      ]
    : []

  // Prepare L2 bar data
  const l2BarData = summary
    ? Object.entries(summary.by_l2).map(([key, val]) => ({
        name: L2_LABELS[key as L2Category] || key,
        code: key,
        amount: val.amount,
        pct: val.pct,
        signal: val.signal,
        color: L2_COLORS[key] || '#9CA3AF',
      }))
    : []

  // Prepare treemap data
  const treemapNodes = treemapData?.nodes ?? []

  // Variance alerts
  const alerts = varianceData?.variances?.slice(0, 6) ?? []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-brand-primary">Dashboard</h1>
          {summary?.plan_name && (
            <p className="text-sm text-gray-500 mt-0.5">
              {summary.plan_name} · FY{summary.fiscal_year}
            </p>
          )}
        </div>
      </div>

      {/* KPI Row */}
      <div className="grid grid-cols-5 gap-4">
        <KpiTile
          label="Total OpEx"
          value={formatCurrency(summary?.total_budget ?? 0, 'USD', true)}
          sub="Annual budget"
        />
        <KpiTile
          label="RTB"
          value={formatCurrency(summary?.rtb.total ?? 0, 'USD', true)}
          sub={`${formatPercent(summary?.rtb.pct ?? 0)} of total`}
          signal={summary?.rtb.signal}
        />
        <KpiTile
          label="CTB"
          value={formatCurrency(summary?.ctb.total ?? 0, 'USD', true)}
          sub={`${formatPercent(summary?.ctb.pct ?? 0)} of total`}
          signal={summary?.ctb.signal}
        />
        <KpiTile
          label="CTB %"
          value={formatPercent(summary?.ctb.pct ?? 0)}
          sub={summary?.ctb.peer_median_pct ? `Peer median: ${formatPercent(summary.ctb.peer_median_pct)}` : undefined}
        />
        <KpiTile
          label="Investments"
          value={String(summary?.investments.active_count ?? 0)}
          sub={`${summary?.investments.at_risk_count ?? 0} at risk`}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-2 gap-6">
        {/* RTB/CTB Donut */}
        <Card>
          <CardHeader>
            <CardTitle>RTB vs CTB Split</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={donutData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {donutData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number) => formatCurrency(value, 'USD', true)}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex justify-center gap-6 mt-2">
              {donutData.map((d) => (
                <div key={d.name} className="flex items-center gap-2 text-sm">
                  <span className="w-3 h-3 rounded-full" style={{ background: d.color }} />
                  <span className="text-gray-600">{d.name}</span>
                  <span className="font-medium text-brand-primary">
                    {formatCurrency(d.value, 'USD', true)}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* L2 Category Bars */}
        <Card>
          <CardHeader>
            <CardTitle>Spend by Category (L2)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={l2BarData}
                  layout="vertical"
                  margin={{ left: 10, right: 40 }}
                >
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#F3F4F6" />
                  <XAxis
                    type="number"
                    tickFormatter={(v) => formatCurrency(v, 'USD', true)}
                    tick={{ fontSize: 11, fill: '#9CA3AF' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={70}
                    tick={{ fontSize: 11, fill: '#6B7280' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatCurrency(value), 'Amount']}
                    cursor={{ fill: '#F9FAFB' }}
                  />
                  <Bar dataKey="amount" radius={[0, 3, 3, 0]} maxBarSize={20}>
                    {l2BarData.map((entry, index) => (
                      <Cell key={index} fill={entry.color} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Treemap */}
      {treemapNodes.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Expense Treemap (L1 → L2)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-72">
              <ResponsiveContainer width="100%" height="100%">
                <Treemap
                  data={treemapNodes}
                  dataKey="value"
                  content={<CustomTreemapContent />}
                />
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Variance Alerts */}
      {alerts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Variance Alerts</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-gray-50">
              {alerts.map((alert, i) => (
                <div key={i} className="flex items-center justify-between px-5 py-3">
                  <div className="flex items-center gap-3">
                    <SignalDot signal={alert.signal} />
                    <div>
                      <p className="text-sm font-medium text-brand-primary">
                        {L2_LABELS[alert.l2_category as L2Category] || alert.l2_category}
                      </p>
                      {alert.signal_reason && (
                        <p className="text-xs text-gray-400">{alert.signal_reason}</p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <Badge signal={alert.signal}>
                      {alert.variance_pct > 0 ? '+' : ''}{formatPercent(alert.variance_pct)}
                    </Badge>
                    <p className="text-xs text-gray-400 mt-0.5">
                      {formatCurrency(Math.abs(alert.variance_amount), 'USD', true)} variance
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
