'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Shield, AlertTriangle, CheckCircle, Info, ClipboardList } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import type { ComplianceData, ComplianceFlag } from '@/lib/types'

// ---------------------------------------------------------------------------
// Compliance score ring
// ---------------------------------------------------------------------------

function ScoreRing({ score }: { score: number }) {
  const color = score >= 90 ? '#4A7C59' : score >= 70 ? '#F59E0B' : '#EF4444'
  const pct = Math.round(score)
  return (
    <div className="flex flex-col items-center justify-center gap-2">
      <div className="relative w-24 h-24">
        <svg className="w-full h-full -rotate-90" viewBox="0 0 36 36">
          <circle cx="18" cy="18" r="15.9155" fill="none" stroke="#F3F4F6" strokeWidth="3" />
          <circle
            cx="18"
            cy="18"
            r="15.9155"
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeDasharray={`${score} ${100 - score}`}
            strokeLinecap="round"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xl font-bold" style={{ color }}>{pct}%</span>
        </div>
      </div>
      <p className="text-xs text-gray-500">Compliance Score</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Flag card
// ---------------------------------------------------------------------------

const FLAG_CONFIG = {
  critical: { dot: 'bg-red-500', badge: 'bg-red-100 text-red-800 border-red-200', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  warning: { dot: 'bg-yellow-500', badge: 'bg-yellow-100 text-yellow-800 border-yellow-200', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  info: { dot: 'bg-blue-500', badge: 'bg-blue-100 text-blue-800 border-blue-200', icon: <Info className="w-3.5 h-3.5" /> },
} as const

function FlagCard({ flag, onResolve }: { flag: ComplianceFlag; onResolve: (id: string) => void }) {
  const cfg = FLAG_CONFIG[flag.severity] ?? FLAG_CONFIG.info
  return (
    <div className="flex border-b border-gray-50 last:border-b-0">
      <div className={`w-1 flex-shrink-0 ${cfg.dot}`} />
      <div className="flex-1 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${cfg.badge}`}>
                {cfg.icon}
                {flag.severity}
              </span>
              <span className="text-xs text-gray-400">{flag.flag_type}</span>
            </div>
            <p className="text-sm font-medium text-gray-800">{flag.item_name}</p>
            <p className="text-xs text-gray-500 mt-0.5">{flag.message}</p>
          </div>
          <Button size="sm" variant="outline" onClick={() => onResolve(flag.id)} className="shrink-0">
            <CheckCircle className="w-3.5 h-3.5 mr-1" />
            Resolve
          </Button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function GuardianPage() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'flags' | 'policy' | 'audit'>('flags')

  const { data, isLoading } = useQuery<ComplianceData>({
    queryKey: ['guardian-data'],
    queryFn: () => api.guardian.data(),
    staleTime: 1000 * 60,
  })

  const resolveMutation = useMutation({
    mutationFn: (flagId: string) => api.guardian.resolveFlag(flagId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['guardian-data'] }),
  })

  const flags = data?.flags ?? []
  const rules = data?.policy_rules ?? []
  const auditLog = data?.audit_log ?? []
  const score = data?.compliance_score ?? 100

  if (isLoading) return <PageSpinner />

  const criticalCount = flags.filter((f) => f.severity === 'critical').length
  const warningCount = flags.filter((f) => f.severity === 'warning').length

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">🛡️</div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">🛡️ Guardian</h1>
          <p className="text-sm text-gray-400 mt-1">
            Compliance Agent · Careful, rule-following, catches what humans miss
          </p>
        </div>

        {/* Overview cards */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-5 flex items-center justify-center">
            <ScoreRing score={score} />
          </Card>
          <Card className="p-5 text-center">
            <p className="text-2xl font-bold text-red-600">{criticalCount}</p>
            <p className="text-xs text-gray-500 mt-1">🔴 Critical Flags</p>
          </Card>
          <Card className="p-5 text-center">
            <p className="text-2xl font-bold text-yellow-600">{warningCount}</p>
            <p className="text-xs text-gray-500 mt-1">🟡 Warnings</p>
          </Card>
          <Card className="p-5 text-center">
            <p className="text-2xl font-bold text-brand-accent">{rules.filter((r) => r.enabled).length}</p>
            <p className="text-xs text-gray-500 mt-1">✅ Active Rules</p>
          </Card>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-100">
          {[
            { key: 'flags', label: `🚩 Flags (${flags.length})` },
            { key: 'policy', label: `📋 Policy Rules` },
            { key: 'audit', label: `🕵️ Audit Log` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as typeof activeTab)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.key
                  ? 'border-brand-accent text-brand-accent'
                  : 'border-transparent text-gray-500 hover:text-brand-primary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Flags tab */}
        {activeTab === 'flags' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Shield className="w-4 h-4 text-brand-accent" />
                Compliance Flags
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {flags.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 gap-3">
                  <CheckCircle className="w-12 h-12 text-green-400" />
                  <p className="text-sm font-medium text-gray-500">All clear — no flags found</p>
                </div>
              ) : (
                <div>
                  {flags.map((flag) => (
                    <FlagCard
                      key={flag.id}
                      flag={flag}
                      onResolve={(id) => resolveMutation.mutate(id)}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Policy rules tab */}
        {activeTab === 'policy' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-brand-accent" />
                Policy Rules
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {rules.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">No policy rules configured.</div>
              ) : (
                <div className="divide-y divide-gray-50">
                  {rules.map((rule) => (
                    <div key={rule.id} className="flex items-center justify-between px-5 py-3">
                      <div>
                        <p className="text-sm font-medium text-gray-800">{rule.name}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{rule.description}</p>
                        {rule.threshold != null && (
                          <p className="text-xs text-gray-400 mt-0.5">Threshold: {rule.threshold}</p>
                        )}
                      </div>
                      <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                        rule.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {rule.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Audit log tab */}
        {activeTab === 'audit' && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Audit Log</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {auditLog.length === 0 ? (
                <div className="text-center py-12 text-gray-400 text-sm">No audit entries yet.</div>
              ) : (
                <div className="divide-y divide-gray-50">
                  {auditLog.map((entry) => (
                    <div key={entry.id} className="flex items-start gap-4 px-5 py-3">
                      <div className="w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center shrink-0">
                        <ClipboardList className="w-3.5 h-3.5 text-gray-500" />
                      </div>
                      <div className="flex-1">
                        <p className="text-sm text-gray-800">
                          <span className="font-medium">{entry.actor}</span>{' '}
                          {entry.action}{' '}
                          <span className="text-brand-accent">{entry.item_name}</span>
                        </p>
                        {entry.details && (
                          <p className="text-xs text-gray-500 mt-0.5">{entry.details}</p>
                        )}
                      </div>
                      <p className="text-xs text-gray-400 shrink-0">
                        {new Date(entry.timestamp).toLocaleString()}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
