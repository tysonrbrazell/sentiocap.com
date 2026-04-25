'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { FileText, Download, RefreshCw, Calendar } from 'lucide-react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Markdown } from '@/components/agents/Markdown'
import type { AgentBoardDeck } from '@/lib/types'

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ScribePage() {
  const [deckPeriod, setDeckPeriod] = useState(() => {
    const d = new Date()
    const q = Math.ceil((d.getMonth() + 1) / 3)
    return `Q${q}-${d.getFullYear()}`
  })
  const [briefingPeriod, setBriefingPeriod] = useState(() => {
    const d = new Date()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    return `${d.getFullYear()}-${m}`
  })
  const [lastDeck, setLastDeck] = useState<AgentBoardDeck | null>(null)
  const [previewContent, setPreviewContent] = useState<string | null>(null)

  const deckMutation = useMutation({
    mutationFn: () => api.agent.boardDeck(deckPeriod),
    onSuccess: (data) => {
      setLastDeck(data)
      setPreviewContent(data.content)
    },
  })

  const briefingMutation = useMutation({
    mutationFn: () => api.scribe.generateBriefing(briefingPeriod),
    onSuccess: (data) => {
      setPreviewContent(data.content)
    },
  })

  function downloadContent(content: string, filename: string) {
    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const busy = deckMutation.isPending || briefingMutation.isPending

  return (
    <div className="min-h-screen relative" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">📝</div>

      <div className="max-w-5xl mx-auto px-6 py-8 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📝 Scribe</h1>
          <p className="text-sm text-gray-400 mt-1">
            Reporting Agent · Articulate, concise, board-ready
          </p>
        </div>

        {/* Generation buttons */}
        <div className="grid grid-cols-2 gap-4">
          {/* Board Deck */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-5 h-5 text-brand-accent" />
              <h3 className="font-semibold text-gray-900">Board Deck</h3>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Quarterly investment review with allocation analysis, benchmarks, and recommendations.
            </p>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg overflow-hidden bg-white">
                <Calendar className="w-4 h-4 text-gray-400 ml-2.5" />
                <input
                  type="text"
                  value={deckPeriod}
                  onChange={(e) => setDeckPeriod(e.target.value)}
                  placeholder="Q1-2025"
                  className="border-0 px-2 py-2 text-sm focus:outline-none w-24"
                />
              </div>
              <Button
                onClick={() => deckMutation.mutate()}
                disabled={busy}
                className="flex items-center gap-2"
              >
                {deckMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <FileText className="w-4 h-4" />
                )}
                {deckMutation.isPending ? 'Generating…' : 'Generate Board Deck'}
              </Button>
            </div>
          </Card>

          {/* Monthly Briefing */}
          <Card className="p-5">
            <div className="flex items-center gap-2 mb-3">
              <FileText className="w-5 h-5 text-purple-600" />
              <h3 className="font-semibold text-gray-900">Monthly Briefing</h3>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              CFO-ready monthly briefing with variance analysis, investment updates, and actions.
            </p>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 border border-gray-200 rounded-lg overflow-hidden bg-white">
                <Calendar className="w-4 h-4 text-gray-400 ml-2.5" />
                <input
                  type="text"
                  value={briefingPeriod}
                  onChange={(e) => setBriefingPeriod(e.target.value)}
                  placeholder="YYYY-MM"
                  className="border-0 px-2 py-2 text-sm focus:outline-none w-28"
                />
              </div>
              <Button
                onClick={() => briefingMutation.mutate()}
                disabled={busy}
                variant="secondary"
                className="flex items-center gap-2"
              >
                {briefingMutation.isPending ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <FileText className="w-4 h-4" />
                )}
                {briefingMutation.isPending ? 'Generating…' : 'Generate Monthly Briefing'}
              </Button>
            </div>
          </Card>
        </div>

        {/* Errors */}
        {deckMutation.isError && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
            {(deckMutation.error as Error).message}
          </div>
        )}
        {briefingMutation.isError && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
            {(briefingMutation.error as Error).message}
          </div>
        )}

        {/* Previously generated reports */}
        {lastDeck && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center justify-between">
                <span className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-brand-accent" />
                  Generated Reports
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              <div className="divide-y divide-gray-50">
                <div className="flex items-center justify-between px-5 py-3">
                  <div>
                    <p className="text-sm font-medium text-gray-800">Board Deck — {lastDeck.period}</p>
                    <p className="text-xs text-gray-400">{new Date(lastDeck.generated_at).toLocaleString()}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setPreviewContent(lastDeck.content)}
                    >
                      Preview
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => downloadContent(lastDeck.content, `board-deck-${lastDeck.period}.md`)}
                    >
                      <Download className="w-3.5 h-3.5 mr-1" />
                      .md
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Preview area */}
        {previewContent && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center justify-between">
                <span>Preview</span>
                <button
                  onClick={() => downloadContent(previewContent, `report-${Date.now()}.md`)}
                  className="text-xs text-brand-accent hover:underline font-medium flex items-center gap-1"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download
                </button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="bg-gray-50 rounded-xl p-5 border border-gray-100 max-h-[600px] overflow-y-auto">
                <Markdown
                  content={
                    previewContent.length > 2000
                      ? previewContent.slice(0, 2000) + '\n\n*…truncated. Download for full report.*'
                      : previewContent
                  }
                />
              </div>
            </CardContent>
          </Card>
        )}

        {/* Empty state */}
        {!lastDeck && !previewContent && (
          <Card>
            <CardContent className="flex flex-col items-center justify-center py-20 gap-4">
              <span className="text-6xl">📝</span>
              <div className="text-center">
                <h3 className="text-base font-medium text-gray-700 mb-1">No reports generated yet</h3>
                <p className="text-sm text-gray-400">
                  Generate a board deck or monthly briefing above to get started.
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
