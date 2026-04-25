'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Send, RefreshCw, Bot } from 'lucide-react'
import { api } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Markdown } from '@/components/agents/Markdown'
import type { AgentAnswer } from '@/lib/types'

// ---------------------------------------------------------------------------
// Suggested questions
// ---------------------------------------------------------------------------

const SUGGESTED = [
  'Why is CTB-GRW underspent this quarter?',
  'What are our top 3 investments at risk?',
  'How do we compare to sector peers on CTB?',
  'Which investments should we consider killing?',
  "What's our full-year forecast vs plan?",
  'Show me our Goldilocks zone position',
]

// ---------------------------------------------------------------------------
// Chat item
// ---------------------------------------------------------------------------

interface ChatItem {
  question: string
  answer: AgentAnswer
}

const CONFIDENCE_COLOR = {
  high: 'text-green-600 bg-green-50 border-green-200',
  medium: 'text-amber-600 bg-amber-50 border-amber-200',
  low: 'text-red-600 bg-red-50 border-red-200',
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SagePage() {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<ChatItem[]>([])

  const mutation = useMutation({
    mutationFn: (q: string) => api.agent.ask(q),
    onSuccess: (data, q) => {
      setHistory((prev) => [{ question: q, answer: data }, ...prev].slice(0, 10))
      setQuestion('')
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || mutation.isPending) return
    mutation.mutate(question.trim())
  }

  function handleSuggested(q: string) {
    setQuestion(q)
    mutation.mutate(q)
  }

  return (
    <div className="min-h-screen relative flex flex-col" style={{ backgroundColor: '#FAFAF8' }}>
      {/* Watermark */}
      <div className="absolute top-6 right-8 text-[96px] opacity-5 pointer-events-none select-none">💬</div>

      <div className="max-w-3xl mx-auto w-full px-6 py-8 flex flex-col flex-1 gap-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-900">💬 Sage</h1>
          <p className="text-sm text-gray-400 mt-1">
            Conversational Agent · Thoughtful, cites data, suggests follow-ups
          </p>
        </div>

        {/* Suggested questions (show only when no history) */}
        {history.length === 0 && !mutation.isPending && (
          <div>
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-3">
              Try asking…
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED.map((q, i) => (
                <button
                  key={i}
                  onClick={() => handleSuggested(q)}
                  className="text-sm px-4 py-2 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-brand-accent hover:text-brand-accent transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex gap-2 sticky bottom-6 z-10">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask anything about your capital allocation…"
            className="flex-1 px-4 py-3 rounded-xl border border-gray-200 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-brand-accent focus:border-transparent placeholder:text-gray-400 shadow-sm"
            disabled={mutation.isPending}
            autoFocus
          />
          <Button
            type="submit"
            disabled={!question.trim() || mutation.isPending}
            className="px-5 py-3 flex items-center gap-2"
          >
            {mutation.isPending ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            Ask
          </Button>
        </form>

        {/* Thinking */}
        {mutation.isPending && (
          <div className="flex items-center gap-2 text-sm text-gray-500 py-2">
            <Bot className="w-4 h-4 animate-pulse text-brand-accent" />
            Thinking…
          </div>
        )}

        {/* Error */}
        {mutation.isError && (
          <div className="text-sm text-red-600 bg-red-50 px-4 py-2.5 rounded-lg border border-red-200">
            {(mutation.error as Error).message}
          </div>
        )}

        {/* Chat history */}
        {history.length > 0 && (
          <div className="space-y-5">
            {history.map((item, i) => (
              <div key={i} className="rounded-2xl border border-gray-100 overflow-hidden bg-white shadow-sm">
                {/* Question */}
                <div className="bg-gray-50 px-5 py-3.5 border-b border-gray-100">
                  <p className="text-sm font-medium text-gray-800">💬 {item.question}</p>
                </div>

                {/* Answer */}
                <div className="p-5 space-y-4">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium px-2.5 py-0.5 rounded-full border ${CONFIDENCE_COLOR[item.answer.confidence]}`}>
                      {item.answer.confidence} confidence
                    </span>
                  </div>

                  <Markdown content={item.answer.answer} />

                  {/* Supporting data */}
                  {item.answer.supporting_data.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {item.answer.supporting_data.map((d, j) => (
                        <span key={j} className="text-xs px-2 py-1 bg-blue-50 text-blue-700 rounded-md border border-blue-100">
                          {d}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Follow-up chips */}
                  {item.answer.follow_up_questions.length > 0 && (
                    <div className="pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-400 mb-2">Ask next:</p>
                      <div className="flex flex-wrap gap-1.5">
                        {item.answer.follow_up_questions.map((q, j) => (
                          <button
                            key={j}
                            onClick={() => handleSuggested(q)}
                            className="text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-brand-accent hover:text-brand-accent transition-colors"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
