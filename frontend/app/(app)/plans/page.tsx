'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Link from 'next/link'
import { Plus, FileText } from 'lucide-react'
import { api } from '@/lib/api'
import { formatCurrency, formatDate } from '@/lib/utils'
import { Card } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Table, Thead, Tbody, Tr, Th, Td } from '@/components/ui/Table'
import { PageSpinner } from '@/components/ui/Spinner'
import { PLAN_TYPE_LABELS, PLAN_STATUS_LABELS, PLAN_STATUS_COLORS } from '@/lib/constants'

export default function PlansPage() {
  const qc = useQueryClient()
  const { data, isLoading } = useQuery({
    queryKey: ['plans'],
    queryFn: () => api.plans.list(),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => api.plans.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plans'] }),
  })

  if (isLoading) return <PageSpinner />

  const plans = data?.plans ?? []

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-brand-primary">Plans</h1>
          <p className="text-sm text-gray-500 mt-0.5">{data?.total ?? 0} plans total</p>
        </div>
        <Link href="/plans/new">
          <Button>
            <Plus className="w-4 h-4" />
            New Plan
          </Button>
        </Link>
      </div>

      {plans.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-64 text-center">
          <FileText className="w-12 h-12 text-gray-300 mb-4" />
          <h3 className="text-base font-medium text-gray-600 mb-1">No plans yet</h3>
          <p className="text-sm text-gray-400 mb-4">Create your first operating plan to get started</p>
          <Link href="/plans/new">
            <Button>
              <Plus className="w-4 h-4" />
              Create first plan
            </Button>
          </Link>
        </div>
      ) : (
        <Card>
          <Table>
            <Thead>
              <Tr>
                <Th>Plan Name</Th>
                <Th>Type</Th>
                <Th>Fiscal Year</Th>
                <Th>Status</Th>
                <Th>Total Budget</Th>
                <Th>Line Items</Th>
                <Th>Created</Th>
                <Th></Th>
              </Tr>
            </Thead>
            <Tbody>
              {plans.map((plan) => (
                <Tr key={plan.id}>
                  <Td>
                    <Link
                      href={`/plans/${plan.id}`}
                      className="font-medium text-brand-primary hover:text-brand-accent"
                    >
                      {plan.name}
                    </Link>
                  </Td>
                  <Td className="text-gray-500">{PLAN_TYPE_LABELS[plan.plan_type] || plan.plan_type}</Td>
                  <Td className="text-gray-500">FY{plan.fiscal_year}</Td>
                  <Td>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${PLAN_STATUS_COLORS[plan.status] || 'bg-gray-100 text-gray-700'}`}>
                      {PLAN_STATUS_LABELS[plan.status] || plan.status}
                    </span>
                  </Td>
                  <Td className="font-medium">
                    {plan.total_budget ? formatCurrency(plan.total_budget, 'USD', true) : '—'}
                  </Td>
                  <Td className="text-gray-500">
                    {plan.line_item_count}
                    {plan.classified_count > 0 && (
                      <span className="text-gray-400 text-xs ml-1">
                        ({plan.classified_count} classified)
                      </span>
                    )}
                  </Td>
                  <Td className="text-gray-400">{formatDate(plan.created_at)}</Td>
                  <Td>
                    <button
                      onClick={() => {
                        if (confirm('Archive this plan?')) deleteMutation.mutate(plan.id)
                      }}
                      className="text-xs text-gray-400 hover:text-red-600 transition-colors"
                    >
                      Archive
                    </button>
                  </Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </Card>
      )}
    </div>
  )
}
