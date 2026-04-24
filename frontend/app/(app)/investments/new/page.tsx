'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ChevronLeft, Plus, X } from 'lucide-react'
import { api } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input, Select } from '@/components/ui/Input'
import { Card, CardContent } from '@/components/ui/Card'
import { L2_CATEGORIES, L3_DOMAINS, L2_LABELS, L3_LABELS, BENEFIT_TYPE_OPTIONS } from '@/lib/constants'
import type { BenefitCreate, InvestmentCreate, L2Category, L3Domain } from '@/lib/types'

const STEPS = ['Basic Info', 'Benefits', 'Spend Profile', 'Review']

const L2_OPTIONS = L2_CATEGORIES.map((c) => ({ value: c, label: `${c} — ${L2_LABELS[c]}` }))
const L3_OPTIONS = L3_DOMAINS.map((d) => ({ value: d, label: `${d} — ${L3_LABELS[d]}` }))
const BENEFIT_OPTIONS = BENEFIT_TYPE_OPTIONS.map((t) => ({ value: t, label: t }))

interface BasicInfo {
  name: string
  description: string
  owner: string
  l2_category: string
  l3_domain: string
  start_date: string
  target_completion: string
  planned_total: string
}

export default function NewInvestmentPage() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [basic, setBasic] = useState<BasicInfo>({
    name: '',
    description: '',
    owner: '',
    l2_category: '',
    l3_domain: '',
    start_date: '',
    target_completion: '',
    planned_total: '',
  })

  const [benefits, setBenefits] = useState<BenefitCreate[]>([
    {
      benefit_type: '',
      description: '',
      calculation_method: 'formula',
      formula: '',
      target_value: undefined,
      confidence: 'medium',
    },
  ])

  const [monthlySpend, setMonthlySpend] = useState<Record<string, string>>({})
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

  function updateBasic(field: keyof BasicInfo, value: string) {
    setBasic((prev) => ({ ...prev, [field]: value }))
  }

  function addBenefit() {
    if (benefits.length >= 5) return
    setBenefits((prev) => [
      ...prev,
      { benefit_type: '', description: '', calculation_method: 'formula', confidence: 'medium' },
    ])
  }

  function removeBenefit(i: number) {
    setBenefits((prev) => prev.filter((_, idx) => idx !== i))
  }

  function updateBenefit(i: number, field: string, value: string | number) {
    setBenefits((prev) =>
      prev.map((b, idx) => (idx === i ? { ...b, [field]: value } : b))
    )
  }

  const totalMonthly = months.reduce((sum, m) => sum + (parseFloat(monthlySpend[m] || '0') || 0), 0)

  async function handleSubmit() {
    setLoading(true)
    setError('')

    try {
      const payload: InvestmentCreate = {
        name: basic.name,
        description: basic.description || undefined,
        owner: basic.owner || undefined,
        l2_category: (basic.l2_category as L2Category) || undefined,
        l3_domain: (basic.l3_domain as L3Domain) || undefined,
        start_date: basic.start_date || undefined,
        target_completion: basic.target_completion || undefined,
        planned_total: basic.planned_total ? parseFloat(basic.planned_total) : undefined,
        status: 'proposed',
        benefits: benefits.filter((b) => b.benefit_type && b.description),
      }
      const inv = await api.investments.create(payload)
      router.push(`/investments/${inv.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create investment')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-3xl">
      <div className="mb-6">
        <Link href="/investments" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-brand-primary mb-4">
          <ChevronLeft className="w-4 h-4" />
          Back to Investments
        </Link>
        <h1 className="text-xl font-semibold text-brand-primary">New Investment</h1>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-0 mb-8">
        {STEPS.map((s, i) => (
          <div key={i} className="flex items-center">
            <button
              onClick={() => i < step && setStep(i)}
              className={`flex items-center gap-2 text-sm font-medium transition-colors ${
                i === step
                  ? 'text-brand-accent'
                  : i < step
                  ? 'text-gray-500 cursor-pointer hover:text-brand-primary'
                  : 'text-gray-300 cursor-not-allowed'
              }`}
            >
              <span
                className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                  i === step
                    ? 'bg-brand-accent text-white'
                    : i < step
                    ? 'bg-gray-200 text-gray-600'
                    : 'bg-gray-100 text-gray-300'
                }`}
              >
                {i + 1}
              </span>
              {s}
            </button>
            {i < STEPS.length - 1 && (
              <div className={`w-8 h-px mx-2 ${i < step ? 'bg-gray-300' : 'bg-gray-100'}`} />
            )}
          </div>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {error}
        </div>
      )}

      {/* Step 1: Basic Info */}
      {step === 0 && (
        <Card>
          <CardContent className="space-y-4">
            <Input label="Investment Name" value={basic.name} onChange={(e) => updateBasic('name', e.target.value)} required placeholder="e.g. Cloud Migration" />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                value={basic.description}
                onChange={(e) => updateBasic('description', e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent resize-none"
                placeholder="What will this investment achieve?"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Owner" value={basic.owner} onChange={(e) => updateBasic('owner', e.target.value)} placeholder="Name or team" />
              <Input label="Planned Total ($)" type="number" value={basic.planned_total} onChange={(e) => updateBasic('planned_total', e.target.value)} placeholder="0" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Select label="L2 Category" value={basic.l2_category} onChange={(e) => updateBasic('l2_category', e.target.value)} options={L2_OPTIONS} placeholder="Select category..." />
              <Select label="L3 Domain" value={basic.l3_domain} onChange={(e) => updateBasic('l3_domain', e.target.value)} options={L3_OPTIONS} placeholder="Select domain..." />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <Input label="Start Date" type="date" value={basic.start_date} onChange={(e) => updateBasic('start_date', e.target.value)} />
              <Input label="Target Completion" type="date" value={basic.target_completion} onChange={(e) => updateBasic('target_completion', e.target.value)} />
            </div>
            <div className="flex justify-end pt-2">
              <Button onClick={() => setStep(1)} disabled={!basic.name}>Next: Benefits</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 2: Benefits */}
      {step === 1 && (
        <div className="space-y-4">
          {benefits.map((b, i) => (
            <Card key={i}>
              <CardContent>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-brand-primary">Benefit {i + 1}</h3>
                  {benefits.length > 1 && (
                    <button onClick={() => removeBenefit(i)} className="text-gray-400 hover:text-red-500 transition-colors">
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Select
                      label="Benefit Type"
                      value={b.benefit_type}
                      onChange={(e) => updateBenefit(i, 'benefit_type', e.target.value)}
                      options={BENEFIT_OPTIONS}
                      placeholder="Select type..."
                    />
                    <Select
                      label="Calculation Method"
                      value={b.calculation_method}
                      onChange={(e) => updateBenefit(i, 'calculation_method', e.target.value)}
                      options={[
                        { value: 'formula', label: 'Formula' },
                        { value: 'milestone', label: 'Milestone' },
                        { value: 'proxy', label: 'Proxy' },
                      ]}
                    />
                  </div>
                  <Input label="Description" value={b.description} onChange={(e) => updateBenefit(i, 'description', e.target.value)} placeholder="What value will this deliver?" />
                  <div className="grid grid-cols-2 gap-3">
                    <Input label="Formula (optional)" value={b.formula || ''} onChange={(e) => updateBenefit(i, 'formula', e.target.value)} placeholder="e.g. headcount_saved × avg_salary" />
                    <Input label="Target Value ($)" type="number" value={b.target_value || ''} onChange={(e) => updateBenefit(i, 'target_value', parseFloat(e.target.value))} placeholder="0" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}

          {benefits.length < 5 && (
            <button onClick={addBenefit} className="flex items-center gap-2 text-sm text-brand-accent hover:text-green-700 font-medium">
              <Plus className="w-4 h-4" />
              Add another benefit
            </button>
          )}

          <div className="flex justify-between pt-2">
            <Button variant="outline" onClick={() => setStep(0)}>Back</Button>
            <Button onClick={() => setStep(2)}>Next: Spend Profile</Button>
          </div>
        </div>
      )}

      {/* Step 3: Monthly Spend */}
      {step === 2 && (
        <Card>
          <CardContent className="space-y-4">
            <div>
              <p className="text-sm font-medium text-gray-700 mb-3">Monthly Spend Profile</p>
              <div className="grid grid-cols-4 gap-3">
                {months.map((m) => (
                  <div key={m}>
                    <label className="block text-xs text-gray-500 mb-1">{m}</label>
                    <input
                      type="number"
                      value={monthlySpend[m] || ''}
                      onChange={(e) => setMonthlySpend((prev) => ({ ...prev, [m]: e.target.value }))}
                      placeholder="0"
                      className="w-full px-2 py-1.5 border border-gray-200 rounded text-sm focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent"
                    />
                  </div>
                ))}
              </div>
              <div className="mt-4 pt-3 border-t border-gray-100 flex justify-between text-sm">
                <span className="text-gray-500">Total</span>
                <span className="font-semibold text-brand-primary">${totalMonthly.toLocaleString()}</span>
              </div>
            </div>
            <div className="flex justify-between pt-2">
              <Button variant="outline" onClick={() => setStep(1)}>Back</Button>
              <Button onClick={() => setStep(3)}>Review</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Step 4: Review */}
      {step === 3 && (
        <Card>
          <CardContent className="space-y-5">
            <div>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Investment Details</h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-gray-400">Name:</span> <span className="font-medium ml-1">{basic.name}</span></div>
                <div><span className="text-gray-400">Owner:</span> <span className="font-medium ml-1">{basic.owner || '—'}</span></div>
                <div><span className="text-gray-400">Category:</span> <span className="font-medium ml-1">{basic.l2_category || '—'}</span></div>
                <div><span className="text-gray-400">Planned Total:</span> <span className="font-medium ml-1">${parseFloat(basic.planned_total || '0').toLocaleString()}</span></div>
                <div><span className="text-gray-400">Start:</span> <span className="font-medium ml-1">{basic.start_date || '—'}</span></div>
                <div><span className="text-gray-400">Completion:</span> <span className="font-medium ml-1">{basic.target_completion || '—'}</span></div>
              </div>
            </div>

            {benefits.filter(b => b.benefit_type).length > 0 && (
              <div>
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">Benefits ({benefits.filter(b => b.benefit_type).length})</h3>
                {benefits.filter(b => b.benefit_type).map((b, i) => (
                  <div key={i} className="text-sm py-1.5 border-b border-gray-50 last:border-0">
                    <span className="font-medium">{b.benefit_type}</span>
                    <span className="text-gray-400 mx-2">·</span>
                    <span className="text-gray-600">{b.description}</span>
                    {b.target_value && <span className="text-gray-400 ml-2">(${b.target_value.toLocaleString()} target)</span>}
                  </div>
                ))}
              </div>
            )}

            <div className="flex justify-between pt-2">
              <Button variant="outline" onClick={() => setStep(2)}>Back</Button>
              <Button loading={loading} onClick={handleSubmit}>Create Investment</Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
