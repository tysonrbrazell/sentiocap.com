'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { ChevronLeft, Upload, CheckCircle, Zap } from 'lucide-react'
import { api } from '@/lib/api'
import { formatCurrency, formatPercent, confidenceToLabel, confidenceToSignal } from '@/lib/utils'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table, Thead, Tbody, Tr, Th, Td } from '@/components/ui/Table'
import { PageSpinner } from '@/components/ui/Spinner'
import { PLAN_STATUS_LABELS, PLAN_STATUS_COLORS, PLAN_TYPE_LABELS, L2_LABELS } from '@/lib/constants'
import type { L2Category, L1Type } from '@/lib/types'

export default function PlanDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const qc = useQueryClient()
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [classifying, setClassifying] = useState(false)
  const [approving, setApproving] = useState(false)

  const { data: plan, isLoading } = useQuery({
    queryKey: ['plan', id, page],
    queryFn: () => api.plans.get(id, page, 50),
  })

  const approveMutation = useMutation({
    mutationFn: () => api.plans.approve(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plan', id] })
      setApproving(false)
    },
  })

  async function handleClassify() {
    setClassifying(true)
    try {
      await api.plans.classify(id)
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ['plan', id] })
        setClassifying(false)
      }, 2000)
    } catch {
      setClassifying(false)
    }
  }

  if (isLoading) return <PageSpinner />
  if (!plan) return null

  const lineItems = plan.line_items.filter(
    (item) =>
      !search ||
      item.source_description.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <Link href="/plans" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-primary mb-3">
          <ChevronLeft className="w-4 h-4" />
          Plans
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-brand-primary">{plan.name}</h1>
              <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PLAN_STATUS_COLORS[plan.status] || 'bg-gray-100 text-gray-700'}`}>
                {PLAN_STATUS_LABELS[plan.status] || plan.status}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-0.5">
              {PLAN_TYPE_LABELS[plan.plan_type]} · FY{plan.fiscal_year}
              {plan.total_budget && ` · ${formatCurrency(plan.total_budget, plan.currency, true)} total`}
            </p>
          </div>
          <div className="flex gap-2">
            <Link href={`/plans/${id}/upload`}>
              <Button variant="outline" size="sm">
                <Upload className="w-3.5 h-3.5" />
                Upload
              </Button>
            </Link>
            <Button variant="outline" size="sm" loading={classifying} onClick={handleClassify}>
              <Zap className="w-3.5 h-3.5" />
              Classify All
            </Button>
            {plan.status === 'submitted' && (
              <Button size="sm" loading={approving} onClick={() => {
                setApproving(true)
                approveMutation.mutate()
              }}>
                <CheckCircle className="w-3.5 h-3.5" />
                Approve
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      {plan.summary && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">RTB Total</p>
            <p className="text-lg font-semibold text-blue-600 mt-1">
              {formatCurrency(plan.summary.rtb_total, 'USD', true)}
            </p>
            <p className="text-xs text-gray-400">{formatPercent(plan.summary.rtb_pct)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">CTB Total</p>
            <p className="text-lg font-semibold text-emerald-600 mt-1">
              {formatCurrency(plan.summary.ctb_total, 'USD', true)}
            </p>
            <p className="text-xs text-gray-400">{formatPercent(plan.summary.ctb_pct)}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Line Items</p>
            <p className="text-lg font-semibold text-brand-primary mt-1">{plan.line_items_total}</p>
          </Card>
          <Card className="p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wide">Classified</p>
            <p className="text-lg font-semibold text-brand-primary mt-1">
              {plan.line_items_total > 0
                ? formatPercent((plan.summary.rtb_total + plan.summary.ctb_total > 0 ? 100 : 0))
                : '—'}
            </p>
          </Card>
        </div>
      )}

      {/* Line Items Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Line Items</CardTitle>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search descriptions..."
              className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent w-64"
            />
          </div>
        </CardHeader>
        <Table>
          <Thead>
            <Tr>
              <Th>Description</Th>
              <Th>Cost Center</Th>
              <Th>GL Account</Th>
              <Th>L1</Th>
              <Th>L2</Th>
              <Th>L3</Th>
              <Th>Confidence</Th>
              <Th className="text-right">Annual Total</Th>
            </Tr>
          </Thead>
          <Tbody>
            {lineItems.length === 0 ? (
              <Tr>
                <Td colSpan={8} className="text-center text-gray-400 py-8">
                  {search ? 'No matching items' : 'No line items yet. Upload a CSV to get started.'}
                </Td>
              </Tr>
            ) : (
              lineItems.map((item) => {
                const conf = item.classification_confidence
                const confSignal = conf != null ? confidenceToSignal(conf) : null
                return (
                  <Tr key={item.id}>
                    <Td className="max-w-xs truncate">{item.source_description}</Td>
                    <Td className="text-gray-400">{item.source_cost_center || '—'}</Td>
                    <Td className="text-gray-400">{item.source_gl_account || '—'}</Td>
                    <Td>
                      {item.classified_l1 ? (
                        <Badge variant={item.classified_l1 === 'RTB' ? 'rtb' : 'ctb'}>
                          {item.classified_l1}
                        </Badge>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </Td>
                    <Td>
                      {item.classified_l2 ? (
                        <span className="text-xs text-gray-600">
                          {L2_LABELS[item.classified_l2 as L2Category] || item.classified_l2}
                        </span>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </Td>
                    <Td className="text-xs text-gray-500">{item.classified_l3 || '—'}</Td>
                    <Td>
                      {conf != null && confSignal ? (
                        <div className="flex items-center gap-2">
                          <div className="w-16 bg-gray-100 rounded-full h-1.5">
                            <div
                              className="h-1.5 rounded-full"
                              style={{
                                width: `${conf * 100}%`,
                                background: confSignal === 'GREEN' ? '#22C55E' : confSignal === 'YELLOW' ? '#EAB308' : '#EF4444',
                              }}
                            />
                          </div>
                          <Badge signal={confSignal}>{confidenceToLabel(conf)}</Badge>
                        </div>
                      ) : (
                        <span className="text-gray-300">—</span>
                      )}
                    </Td>
                    <Td className="text-right font-medium">
                      {formatCurrency(item.annual_total)}
                    </Td>
                  </Tr>
                )
              })
            )}
          </Tbody>
        </Table>

        {/* Pagination */}
        {plan.line_items_total > plan.line_items_per_page && (
          <div className="flex items-center justify-between px-5 py-3 border-t border-gray-100">
            <p className="text-sm text-gray-500">
              Page {page} of {Math.ceil(plan.line_items_total / plan.line_items_per_page)}
            </p>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= Math.ceil(plan.line_items_total / plan.line_items_per_page)}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
