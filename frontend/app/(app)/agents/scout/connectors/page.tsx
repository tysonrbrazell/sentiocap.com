'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Link2,
  Link2Off,
  RefreshCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronLeft,
} from 'lucide-react'
import Link from 'next/link'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import type { ConnectorConfig, UnifiedCostView } from '@/lib/types'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const CONNECTOR_META: Record<string, { label: string; icon: string; category: string }> = {
  salesforce: { label: 'Salesforce', icon: '☁️', category: 'CRM' },
  jira:       { label: 'JIRA',        icon: '🎫', category: 'Engineering' },
  hubspot:    { label: 'HubSpot',     icon: '🟠', category: 'CRM' },
  dynamics:   { label: 'Dynamics 365',icon: '🔵', category: 'CRM' },
  workday:    { label: 'Workday',     icon: '🟡', category: 'ERP' },
  sap:        { label: 'SAP',         icon: '⚙️',  category: 'ERP' },
  servicenow: { label: 'ServiceNow',  icon: '🟢', category: 'ITSM' },
}

const MOCK_ENABLED = new Set(['salesforce', 'jira'])

function fmt(n: number | null | undefined, prefix = '$'): string {
  if (n == null || n === 0) return '—'
  if (Math.abs(n) >= 1_000_000) return `${prefix}${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `${prefix}${(n / 1_000).toFixed(0)}K`
  return `${prefix}${n.toFixed(0)}`
}

function fmtPct(n: number | null | undefined): string {
  if (n == null) return '—'
  return `${(n * 100).toFixed(0)}%`
}

function SignalBadge({ signal }: { signal: 'GREEN' | 'YELLOW' | 'RED' }) {
  const cfg = {
    GREEN:  { cls: 'bg-green-100 text-green-700 border-green-200', label: 'Healthy' },
    YELLOW: { cls: 'bg-yellow-100 text-yellow-700 border-yellow-200', label: 'Watch' },
    RED:    { cls: 'bg-red-100 text-red-700 border-red-200', label: 'At Risk' },
  }[signal]
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold border ${cfg.cls}`}>
      {cfg.label}
    </span>
  )
}

function GapCell({ actual, planned }: { actual: number; planned: number }) {
  if (!planned || !actual) return <td className="px-4 py-3 text-gray-400 text-center text-xs">—</td>
  const gap = Math.abs(actual - planned) / planned
  const over = actual > planned
  const isOk = gap <= 0.30
  const cls = isOk
    ? 'text-green-700 bg-green-50'
    : 'text-red-700 bg-red-50'
  const Icon = over ? TrendingUp : TrendingDown
  return (
    <td className={`px-4 py-3 text-center`}>
      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${cls}`}>
        <Icon className="w-3 h-3" />
        {fmtPct(gap)}
      </span>
    </td>
  )
}

function StatusBadge({ status }: { status: string }) {
  const cfg: Record<string, { cls: string; icon: React.ReactNode }> = {
    connected:    { cls: 'text-green-700 bg-green-50 border-green-200', icon: <CheckCircle2 className="w-3.5 h-3.5" /> },
    disconnected: { cls: 'text-gray-500 bg-gray-50 border-gray-200', icon: <XCircle className="w-3.5 h-3.5" /> },
    syncing:      { cls: 'text-blue-700 bg-blue-50 border-blue-200', icon: <Loader2 className="w-3.5 h-3.5 animate-spin" /> },
    error:        { cls: 'text-red-700 bg-red-50 border-red-200', icon: <AlertTriangle className="w-3.5 h-3.5" /> },
  }
  const c = cfg[status] ?? cfg.disconnected
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${c.cls}`}>
      {c.icon}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Connector card
// ---------------------------------------------------------------------------

function ConnectorCard({ connector, onConnect, onDisconnect, onSync, loading }: {
  connector: ConnectorConfig
  onConnect: (type: string) => void
  onDisconnect: (type: string) => void
  onSync: (type: string) => void
  loading: string | null
}) {
  const meta = CONNECTOR_META[connector.connector_type] ?? {
    label: connector.connector_type, icon: '🔌', category: 'Other'
  }
  const isConnected = connector.status === 'connected' || connector.status === 'syncing'
  const isMockAvailable = MOCK_ENABLED.has(connector.connector_type)
  const isLoading = loading === connector.connector_type

  return (
    <Card className="relative overflow-hidden">
      {/* Category label */}
      <div className="absolute top-3 right-3">
        <span className="text-xs text-gray-400 font-medium">{meta.category}</span>
      </div>

      <CardContent className="p-5">
        <div className="flex items-start gap-3">
          <span className="text-2xl">{meta.icon}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="font-semibold text-gray-900">{meta.label}</h3>
              <StatusBadge status={connector.status} />
              {isMockAvailable && !isConnected && (
                <span className="text-xs text-purple-600 bg-purple-50 border border-purple-200 px-1.5 py-0.5 rounded-full">
                  Mock available
                </span>
              )}
            </div>

            {isConnected && connector.last_sync_at && (
              <p className="text-xs text-gray-400 mt-1">
                Last sync: {new Date(connector.last_sync_at).toLocaleString()}
              </p>
            )}

            {connector.last_sync && (
              <p className="text-xs text-gray-500 mt-1">
                {connector.last_sync.records_synced.toLocaleString()} records synced
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 mt-4">
          {isConnected ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onSync(connector.connector_type)}
                disabled={isLoading || connector.status === 'syncing'}
                className="flex items-center gap-1.5"
              >
                {isLoading ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="w-3.5 h-3.5" />
                )}
                Sync Now
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => onDisconnect(connector.connector_type)}
                disabled={isLoading}
                className="flex items-center gap-1.5 text-red-600 hover:bg-red-50 hover:border-red-200"
              >
                <Link2Off className="w-3.5 h-3.5" />
                Disconnect
              </Button>
            </>
          ) : (
            <Button
              size="sm"
              onClick={() => onConnect(connector.connector_type)}
              disabled={isLoading || !isMockAvailable}
              className="flex items-center gap-1.5"
            >
              {isLoading ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Link2 className="w-3.5 h-3.5" />
              )}
              {isMockAvailable ? 'Connect (Mock)' : 'Coming Soon'}
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Unified cost table row
// ---------------------------------------------------------------------------

function CostRow({ view }: { view: UnifiedCostView }) {
  const layerGap = view.planned_cost > 0 && view.gl_actual_cost > 0
    ? Math.abs(view.gl_actual_cost - view.planned_cost) / view.planned_cost
    : null
  const hasSignals = view.health_signals.length > 0

  return (
    <tr className="hover:bg-gray-50/80 transition-colors group">
      <td className="px-4 py-3">
        <div className="flex items-start gap-2">
          <div>
            <div className="font-medium text-gray-900 text-sm">{view.investment_name}</div>
            {view.l2_category && (
              <span className="text-xs font-mono text-gray-400">{view.l2_category}</span>
            )}
          </div>
        </div>
      </td>
      <td className="px-4 py-3 text-sm text-gray-700 text-right font-mono">
        {fmt(view.planned_cost)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-700 text-right font-mono">
        {fmt(view.gl_actual_cost)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-700 text-right font-mono">
        {fmt(view.effort_cost)}
      </td>
      <td className="px-4 py-3 text-sm text-gray-700 text-right font-mono">
        {fmt(view.revenue_pipeline)}
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono">
        {view.revenue_closed > 0 ? (
          <span className="text-green-700 font-semibold">{fmt(view.revenue_closed)}</span>
        ) : (
          <span className="text-gray-400">—</span>
        )}
      </td>
      {/* Deployment rate */}
      <td className="px-4 py-3 text-center">
        {view.deployment_rate != null ? (
          <span className={`text-xs font-semibold ${
            view.deployment_rate >= 0.8 ? 'text-green-700' :
            view.deployment_rate >= 0.5 ? 'text-yellow-700' : 'text-red-700'
          }`}>
            {fmtPct(view.deployment_rate)}
          </span>
        ) : <span className="text-gray-400 text-xs">—</span>}
      </td>
      {/* ROI on plan */}
      <td className="px-4 py-3 text-center">
        {view.roi_on_plan != null ? (
          <span className={`text-xs font-semibold ${
            view.roi_on_plan >= 1.5 ? 'text-green-700' :
            view.roi_on_plan >= 0.8 ? 'text-yellow-700' : 'text-red-700'
          }`}>
            {fmtPct(view.roi_on_plan)}
          </span>
        ) : <span className="text-gray-400 text-xs">—</span>}
      </td>
      {/* GL vs Plan gap */}
      <GapCell actual={view.gl_actual_cost} planned={view.planned_cost} />
      {/* Signal */}
      <td className="px-4 py-3 text-center">
        <div className="flex flex-col items-center gap-1">
          <SignalBadge signal={view.signal} />
          {hasSignals && (
            <span className="text-xs text-gray-400">
              {view.health_signals.length} signal{view.health_signals.length > 1 ? 's' : ''}
            </span>
          )}
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function ConnectorsPage() {
  const queryClient = useQueryClient()
  const [loadingConnector, setLoadingConnector] = useState<string | null>(null)
  const [syncMsg, setSyncMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const { data: connectors, isLoading: connectorsLoading } = useQuery<ConnectorConfig[]>({
    queryKey: ['connectors'],
    queryFn: () => api.connectors.list(),
    staleTime: 30_000,
  })

  const { data: unifiedCost, isLoading: costLoading } = useQuery<UnifiedCostView[]>({
    queryKey: ['unified-cost'],
    queryFn: () => api.connectors.unifiedCost(),
    staleTime: 60_000,
  })

  const handleConnect = async (type: string) => {
    setLoadingConnector(type)
    setSyncMsg(null)
    try {
      await api.connectors.connect(type)
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
      setSyncMsg({ type: 'success', text: `${CONNECTOR_META[type]?.label ?? type} connected successfully` })
    } catch (err) {
      setSyncMsg({ type: 'error', text: (err as Error).message ?? 'Connection failed' })
    } finally {
      setLoadingConnector(null)
    }
  }

  const handleDisconnect = async (type: string) => {
    setLoadingConnector(type)
    try {
      await api.connectors.disconnect(type)
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
      setSyncMsg({ type: 'success', text: `${CONNECTOR_META[type]?.label ?? type} disconnected` })
    } catch (err) {
      setSyncMsg({ type: 'error', text: (err as Error).message ?? 'Disconnect failed' })
    } finally {
      setLoadingConnector(null)
    }
  }

  const handleSync = async (type: string) => {
    setLoadingConnector(type)
    setSyncMsg(null)
    try {
      const result = await api.connectors.sync(type)
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
      queryClient.invalidateQueries({ queryKey: ['unified-cost'] })
      setSyncMsg({
        type: result.status === 'completed' ? 'success' : 'error',
        text: result.status === 'completed'
          ? `Sync complete — ${result.records_synced} records synced`
          : `Sync ${result.status}: ${result.errors[0]?.message ?? 'unknown error'}`,
      })
    } catch (err) {
      setSyncMsg({ type: 'error', text: (err as Error).message ?? 'Sync failed' })
    } finally {
      setLoadingConnector(null)
    }
  }

  if (connectorsLoading) return <PageSpinner />

  const connectedCount = connectors?.filter(c => c.status === 'connected' || c.status === 'syncing').length ?? 0
  const totalRecords = connectors?.reduce((sum, c) => sum + (c.last_sync?.records_synced ?? 0), 0) ?? 0

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">
        🔌
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 space-y-8">

        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link
              href="/agents/scout"
              className="text-sm text-gray-400 hover:text-gray-600 flex items-center gap-1 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              Scout
            </Link>
          </div>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
                🔌 Data Connectors
              </h1>
              <p className="text-sm text-gray-400 mt-1">
                Connect Salesforce, JIRA & ERPs to unlock true investment cost visibility
              </p>
            </div>
            <div className="flex gap-4 text-center">
              <div>
                <div className="text-xl font-bold text-gray-900">{connectedCount}</div>
                <div className="text-xs text-gray-500">Connected</div>
              </div>
              <div>
                <div className="text-xl font-bold" style={{ color: '#4A7C59' }}>{totalRecords.toLocaleString()}</div>
                <div className="text-xs text-gray-500">Records synced</div>
              </div>
            </div>
          </div>
        </div>

        {/* Notification */}
        {syncMsg && (
          <div className={`text-sm px-4 py-2.5 rounded-lg border flex items-center gap-2 ${
            syncMsg.type === 'success'
              ? 'text-green-700 bg-green-50 border-green-200'
              : 'text-red-700 bg-red-50 border-red-200'
          }`}>
            {syncMsg.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            )}
            {syncMsg.text}
          </div>
        )}

        {/* Connector cards */}
        <div>
          <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wider mb-3">
            Integrations
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {(connectors ?? []).map(connector => (
              <ConnectorCard
                key={connector.connector_type}
                connector={connector}
                onConnect={handleConnect}
                onDisconnect={handleDisconnect}
                onSync={handleSync}
                loading={loadingConnector}
              />
            ))}
          </div>
        </div>

        {/* Cost layer explainer */}
        <Card className="bg-gradient-to-r from-slate-50 to-gray-50 border-slate-200">
          <CardContent className="p-5">
            <h3 className="text-sm font-semibold text-gray-700 mb-3">
              The 3 Cost Layers SentioCap Reconciles
            </h3>
            <div className="grid grid-cols-3 gap-4 text-sm">
              {[
                { icon: '📋', label: 'Planned Cost', desc: 'Budget / investment plan' },
                { icon: '🏦', label: 'GL Actual', desc: 'Real dollars from ERP/GL' },
                { icon: '⚡', label: 'Effort Cost', desc: 'Hours × rate from JIRA' },
              ].map(({ icon, label, desc }) => (
                <div key={label} className="flex items-start gap-2">
                  <span className="text-lg">{icon}</span>
                  <div>
                    <div className="font-semibold text-gray-800">{label}</div>
                    <div className="text-xs text-gray-500">{desc}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-xs text-gray-400 border-t border-gray-200 pt-3">
              Gap between layers = where money disappears. Connect Salesforce + JIRA to see the full picture.
            </div>
          </CardContent>
        </Card>

        {/* Unified Investment Cost Table */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wider">
              Unified Investment Cost View
            </h2>
            <Button
              size="sm"
              variant="outline"
              onClick={() => queryClient.invalidateQueries({ queryKey: ['unified-cost'] })}
              className="flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Refresh
            </Button>
          </div>

          <Card>
            {costLoading ? (
              <div className="flex items-center justify-center py-16 text-gray-400">
                <Loader2 className="w-6 h-6 animate-spin mr-2" />
                Loading investment data…
              </div>
            ) : !unifiedCost || unifiedCost.length === 0 ? (
              <div className="text-center py-16 text-gray-400">
                <div className="text-3xl mb-3">🔌</div>
                <div className="font-medium text-gray-600">No investment data yet</div>
                <div className="text-sm mt-1">
                  Connect Salesforce and JIRA above, then sync to populate cost layers.
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-gray-100 bg-gray-50/50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Investment
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        📋 Planned
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        🏦 GL Actual
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        ⚡ Effort
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Pipeline
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Closed Won
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Deploy %
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        ROI
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Gap
                      </th>
                      <th className="px-4 py-3 text-center text-xs font-semibold text-gray-500 uppercase tracking-wide">
                        Signal
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {unifiedCost.map(view => (
                      <CostRow key={view.investment_id} view={view} />
                    ))}
                  </tbody>
                </table>

                {/* Legend */}
                <div className="px-4 py-3 border-t border-gray-100 bg-gray-50/30 flex items-center gap-6 text-xs text-gray-500">
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-2 rounded bg-green-100 border border-green-200 inline-block" />
                    Gap ≤ 30% — layers align
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-3 h-2 rounded bg-red-100 border border-red-200 inline-block" />
                    Gap &gt; 30% — investigate
                  </span>
                  <span className="ml-auto italic">
                    Deploy % = GL actual / planned · ROI = closed won / planned
                  </span>
                </div>
              </div>
            )}
          </Card>
        </div>

      </div>
    </div>
  )
}
