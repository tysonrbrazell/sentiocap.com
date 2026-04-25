'use client'

import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Upload, CheckCircle, Clock, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { PageSpinner } from '@/components/ui/Spinner'
import type { ScoutStats } from '@/lib/types'

// ---------------------------------------------------------------------------
// Confidence badge
// ---------------------------------------------------------------------------

function ConfidenceBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const cls =
    score >= 0.85
      ? 'bg-green-100 text-green-700 border-green-200'
      : score >= 0.65
      ? 'bg-yellow-100 text-yellow-700 border-yellow-200'
      : 'bg-red-100 text-red-700 border-red-200'
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${cls}`}>
      {pct}%
    </span>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ScoutPage() {
  const queryClient = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<string | null>(null)

  const { data: stats, isLoading } = useQuery<ScoutStats>({
    queryKey: ['scout-stats'],
    queryFn: () => api.scout.stats(),
    staleTime: 1000 * 60,
  })

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadMsg(null)
    try {
      const result = await api.scout.uploadDocument(file)
      setUploadMsg(result.message)
      queryClient.invalidateQueries({ queryKey: ['scout-stats'] })
    } catch (err: unknown) {
      setUploadMsg((err as Error).message ?? 'Upload failed')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  if (isLoading) return <PageSpinner />

  const accuracy = stats?.accuracy_pct ?? 0

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Emoji watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">
        🔍
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2.5">
              🔍 Scout
            </h1>
            <p className="text-sm text-gray-400 mt-1">
              Classification Agent · Meticulous, never sleeps, catches everything
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              ref={fileRef}
              type="file"
              accept=".pdf,.xlsx,.xls,.pptx,.csv"
              className="hidden"
              onChange={handleUpload}
            />
            <Button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              {uploading ? 'Uploading…' : 'Upload Document'}
            </Button>
          </div>
        </div>

        {uploadMsg && (
          <div className="text-sm text-green-700 bg-green-50 px-4 py-2.5 rounded-lg border border-green-200">
            {uploadMsg}
          </div>
        )}

        {/* Stats row */}
        <div className="grid grid-cols-4 gap-4">
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold" style={{ color: '#4A7C59' }}>
              {(stats?.total_classified ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-gray-500 mt-1">Total Classified</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-blue-600">
              {(stats?.confirmed_count ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-gray-500 mt-1">Human Confirmed</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-purple-600">{accuracy.toFixed(1)}%</p>
            <p className="text-xs text-gray-500 mt-1">Accuracy Rate</p>
          </Card>
          <Card className="p-4 text-center">
            <p className="text-2xl font-bold text-yellow-600">
              {stats?.pending_review ?? 0}
            </p>
            <p className="text-xs text-gray-500 mt-1">Pending Review</p>
          </Card>
        </div>

        {/* Recent classifications */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <RefreshCw className="w-4 h-4 text-brand-accent" />
              Recent Classifications
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {!stats?.recent || stats.recent.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">
                No classifications yet. Upload a document to get started.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-gray-100">
                    <tr>
                      <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">Description</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">L1</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">L2</th>
                      <th className="px-5 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide">L4</th>
                      <th className="px-5 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">Confidence</th>
                      <th className="px-5 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wide">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {stats.recent.map((item) => (
                      <tr key={item.id} className="hover:bg-gray-50 transition-colors">
                        <td className="px-5 py-3 font-medium text-gray-800 max-w-xs truncate">
                          {item.source_description}
                        </td>
                        <td className="px-5 py-3 text-gray-600 font-mono text-xs">{item.classified_l1}</td>
                        <td className="px-5 py-3 text-gray-600 font-mono text-xs">{item.classified_l2}</td>
                        <td className="px-5 py-3 text-gray-500 text-xs">{item.classified_l4 || '—'}</td>
                        <td className="px-5 py-3 text-center">
                          <ConfidenceBadge score={item.confidence} />
                        </td>
                        <td className="px-5 py-3 text-center">
                          {item.confirmed ? (
                            <CheckCircle className="w-4 h-4 text-green-500 mx-auto" />
                          ) : (
                            <Clock className="w-4 h-4 text-yellow-500 mx-auto" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Classification queue */}
        {(stats?.pending_review ?? 0) > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base text-yellow-700 flex items-center gap-2">
                <Clock className="w-4 h-4" />
                Classification Queue ({stats?.pending_review} items need review)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-gray-500">
                Review pending items in the <a href="/plans" className="text-brand-accent underline">Plans</a> section or use Sage to ask about specific items.
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
