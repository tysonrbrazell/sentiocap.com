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
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
} from 'recharts'
import { api } from '@/lib/api'
import { formatPercent } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { PageSpinner } from '@/components/ui/Spinner'
import { SECTORS, L2_LABELS } from '@/lib/constants'
import type { L2Category } from '@/lib/types'

export default function BenchmarksPage() {
  const [sector, setSector] = useState(SECTORS[0])

  const { data, isLoading } = useQuery({
    queryKey: ['benchmarks', sector],
    queryFn: () => api.benchmarks.compare(sector),
  })

  const comparison = data?.comparison ?? []

  const barData = comparison.map((item) => ({
    name: L2_LABELS[item.l2_category as L2Category] || item.l2_category,
    'Your %': item.org_pct ?? 0,
    'Peer Median': item.peer_median ?? 0,
    'P25': item.peer_p25 ?? 0,
    'P75': item.peer_p75 ?? 0,
  }))

  const radarData = comparison.map((item) => ({
    category: item.l2_category,
    org: item.org_pct ?? 0,
    median: item.peer_median ?? 0,
  }))

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-brand-primary">Benchmarks</h1>
          <p className="text-sm text-gray-500 mt-0.5">Compare your spend allocation to sector peers</p>
        </div>

        <select
          value={sector}
          onChange={(e) => setSector(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent bg-white"
        >
          {SECTORS.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
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
          {/* Bar Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Spend Allocation vs Sector Benchmarks — {sector}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ left: 10, right: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#F3F4F6" />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11, fill: '#6B7280' }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tickFormatter={(v) => `${v}%`}
                      tick={{ fontSize: 11, fill: '#9CA3AF' }}
                      axisLine={false}
                      tickLine={false}
                    />
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

          {/* Comparison Table */}
          <Card>
            <CardHeader>
              <CardTitle>Detailed Comparison</CardTitle>
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
                    {comparison.map((item) => (
                      <tr key={item.l2_category}>
                        <td className="px-5 py-3 font-medium text-brand-primary">
                          <div>{item.l2_category}</div>
                          <div className="text-xs text-gray-400">
                            {L2_LABELS[item.l2_category as L2Category] || ''}
                          </div>
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
                        <td className="px-5 py-3 text-xs text-gray-400 max-w-xs">
                          {item.insight || '—'}
                        </td>
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
  )
}
