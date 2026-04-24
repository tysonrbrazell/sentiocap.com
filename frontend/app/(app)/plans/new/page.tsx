'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ChevronLeft } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Input'
import { Card, CardContent } from '@/components/ui/Card'

const PLAN_TYPE_OPTIONS = [
  { value: 'annual_budget', label: 'Annual Budget' },
  { value: 'reforecast', label: 'Reforecast' },
  { value: 'scenario', label: 'Scenario' },
]

const currentYear = new Date().getFullYear()
const YEAR_OPTIONS = [-1, 0, 1, 2].map((offset) => ({
  value: String(currentYear + offset),
  label: `FY${currentYear + offset}`,
}))

export default function NewPlanPage() {
  const router = useRouter()
  const [form, setForm] = useState({
    name: '',
    plan_type: 'annual_budget' as const,
    fiscal_year: currentYear,
    notes: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  function update(field: string, value: string | number) {
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const plan = await api.plans.create({
        name: form.name,
        plan_type: form.plan_type,
        fiscal_year: Number(form.fiscal_year),
        notes: form.notes || undefined,
      })
      router.push(`/plans/${plan.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create plan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <Link href="/plans" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-primary mb-4">
          <ChevronLeft className="w-4 h-4" />
          Back to Plans
        </Link>
        <h1 className="text-xl font-semibold text-brand-primary">Create New Plan</h1>
        <p className="text-sm text-gray-500 mt-0.5">Set up your operating plan details</p>
      </div>

      <Card>
        <CardContent>
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <Input
              label="Plan Name"
              value={form.name}
              onChange={(e) => update('name', e.target.value)}
              required
              placeholder="e.g. FY2025 Annual Budget"
            />

            <div className="grid grid-cols-2 gap-4">
              <Select
                label="Plan Type"
                value={form.plan_type}
                onChange={(e) => update('plan_type', e.target.value)}
                options={PLAN_TYPE_OPTIONS}
              />
              <Select
                label="Fiscal Year"
                value={String(form.fiscal_year)}
                onChange={(e) => update('fiscal_year', e.target.value)}
                options={YEAR_OPTIONS}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Notes (optional)</label>
              <textarea
                value={form.notes}
                onChange={(e) => update('notes', e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent resize-none"
                placeholder="Any additional context..."
              />
            </div>

            <div className="flex gap-3 pt-2">
              <Button type="submit" loading={loading}>
                Create Plan
              </Button>
              <Link href="/plans">
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
