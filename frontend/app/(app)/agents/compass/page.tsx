'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { api } from '@/lib/api'
import { formatPercent } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { SECTORS, L2_LABELS } from '@/lib/constants'
import type { L2Category } from '@/lib/types'

// ---------------------------------------------------------------------------
// Goldilocks indicator
// ---------------------------------------------------------------------------

function GoldilocksIndicator({ ctbPct }: { ctbPct: number }) {
  const inZone = ctbPct >= 10 && ctbPct <= 20
  return (
    <Card className="p-5">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Goldilocks Zone (10–20% CTB)
      </h3>
      <div className="relative h-6 bg-gray-100 rounded-full overflow-hidden">
        {/* Zone highlight */}
        <div
          className="absolute top-0 h-full bg-green-100 border-l border-r border-green-300"
          style={{ left: '10%', width: '10%' }}
        />
        {/* Your position */}
        <div
          className="absolute top-0 h-full w-1 bg-brand-accent rounded"
          style={{ left: `${Math.min(Math.max(ctbPct, 0), 50) * 2}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-400 mt-1.5">
        <span>0%</span>
        <span>25%</span>
        <span>50%</span>
      </div>
      <div className={`mt-3 text-sm font-medium ${inZone ? 'text-green-700' : 'text-yellow-700'}`}>
        {inZone
          ? `✅ You're in the Goldilocks zone at ${ctbPct.toFixed(1)}% CTB`
          : `⚠️ CTB at ${ctbPct.toFixed(1)}% — outside 10–20% target range`}
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CompassPage() {
  const [sector, setSector] = useState(SECTORS[0])

  const { data, isLoading } = useQuery({
    queryKey: ['benchmarks', sector],
    queryFn: () => api.benchmarks.compare(sector),
  })

  const comparison = data?.comparison ?? []
  const ctbPct =
    comparison
      .filter((c) => c.l2_category.startsWith('CTB'))
      .reduce((sum, c) => sum + (c.org_pct ?? 0), 0)

  const barData = comparison.map((item) => ({
    name: L2_LABELS[item.l2_category as L2Category] || item.l2_category,
    'Your %': item.org_pct ?? 0,
    'Peer Median': item.peer_median ?? 0,
    P25: item.peer_p25 ?? 0,
    P75: item.peer_p75 ?? 0,
  }))

  // Peer ranking — sort by org_pct descending relative to median
  const ranked = [...comparison]
    .sort((a, b) => ((b.org_pct ?? 0) - (b.peer_median ?? 0)) - ((a.org_pct ?? 0) - (a.peer_median ?? 0)))

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">📊</div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">📊 Compass</h1>
            <p className="text-sm text-gray-400 mt-1">
              Benchmarking Agent · Competitive, data-obsessed, sees the full landscape
            </p>
          </div>
          <select
            value={sector}
            onChange={(e) => setSector(e.target.value)}
            className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent bg-white"
          >
            {SECTORS.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        {isLoading && <PageSpinner />}

        {!isLoading && comparison.length === 0 && (
          <Card>
            <CardContent className="text-center py-16">
              <p className="text-gray-400">No benchmark data available for {sector}</p>
            </CardContent>
          </Card>
        )}

        {!isLoading && comparison.length > 0 && (
          <>
            {/* Your Position summary card */}
            <div className="grid grid-cols-3 gap-4">
              <Card className="p-5 col-span-2">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
                  Your Position — {sector}
                </h3>
                <div className="grid grid-cols-3 gap-4">
                  {comparison.slice(0, 3).map((item) => (
                    <div key={item.l2_category}>
                      <p className="text-lg font-bold text-gray-900">
                        {item.org_pct != null ? `${item.org_pct.toFixed(1)}%` : '—'}
                      </p>
                      <p className="text-xs text-gray-500">{item.l2_category}</p>
                      <p className="text-xs text-gray-400">
                        Median: {item.peer_median != null ? `${item.peer_median.toFixed(1)}%` : '—'}
                      </p>
                    </div>
                  ))}
                </div>
              </Card>
              <GoldilocksIndicator ctbPct={ctbPct} />
            </div>

            {/* Bar chart */}
            <Card>
              <CardHeader>
                <CardTitle>Spend Allocation vs Sector Benchmarks — {sector}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={barData} margin={{ left: 10, right: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6B7280' }} axisLine={false} tickLine={false} />
                      <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: '#9CA3AF' }} axisLine={false} tickLine={false} />
                      <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`]} />
                      <Legend />
                      <Bar dataKey="Your %" fill="#4A7C59" radius={[3, 3, 0, 0]} maxBarSize={30} />
                      <Bar dataKey="Peer Median" fill="#9CA3AF" radius={[3, 3, 0, 0]} maxBarSize={30} />
                      <Bar dataKey="P25" fill="#D1FAE5" radius={[3, 3, 0, 0]} maxBarSize={30} />
                      <Bar dataKey="P75" fill="#6EE7B7" radius={[3, 3, 0, 0]} maxBarSize={30} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* Peer ranking table */}
            <Card>
              <CardHeader>
                <CardTitle>Peer Ranking — vs Median</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="border-b border-gray-100">
                      <tr>
                        <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Category</th>
                        <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Your %</th>
                        <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">P25</th>
                        <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">Median</th>
                        <th className="px-5 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">P75</th>
                        <th className="px-5 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">Signal</th>
                        <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Insight</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50">
                      {ranked.map((item) => (
                        <tr key={item.l2_category} className="hover:bg-gray-50">
                          <td className="px-5 py-3 font-medium text-brand-primary">
                            <div>{item.l2_category}</div>
                            <div className="text-xs text-gray-400">{L2_LABELS[item.l2_category as L2Category] || ''}</div>
                          </td>
                          <td className="px-5 py-3 text-right font-semibold">
                            {item.org_pct != null ? formatPercent(item.org_pct) : '—'}
                          </td>
                          <td className="px-5 py-3 text-right text-gray-500">
                            {item.peer_p25 != null ? formatPercent(item.peer_p25) : '—'}
                          </td>
                          <td className="px-5 py-3 text-right text-gray-500">
                            {item.peer_median != null ? formatPercent(item.peer_median) : '—'}
                          </td>
                          <td className="px-5 py-3 text-right text-gray-500">
                            {item.peer_p75 != null ? formatPercent(item.peer_p75) : '—'}
                          </td>
                          <td className="px-5 py-3 text-center">
                            <Badge signal={item.signal}>{item.signal}</Badge>
                          </td>
                          <td className="px-5 py-3 text-xs text-gray-400 max-w-xs">{item.insight || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  )
}
