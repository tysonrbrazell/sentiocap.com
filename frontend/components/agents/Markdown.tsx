// Lightweight Markdown renderer — shared across all agent pages
export function Markdown({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <div className="prose prose-sm max-w-none text-gray-700 space-y-2">
      {lines.map((line, i) => {
        if (line.startsWith('## ')) {
          return (
            <h2 key={i} className="text-base font-semibold text-gray-900 mt-4 mb-1">
              {line.slice(3)}
            </h2>
          )
        }
        if (line.startsWith('### ')) {
          return (
            <h3 key={i} className="text-sm font-semibold text-gray-800 mt-3 mb-1">
              {line.slice(4)}
            </h3>
          )
        }
        if (line.startsWith('- ') || line.startsWith('• ')) {
          return (
            <div key={i} className="flex gap-2 ml-2">
              <span className="text-gray-400 mt-0.5">•</span>
              <span dangerouslySetInnerHTML={{ __html: boldInline(line.slice(2)) }} />
            </div>
          )
        }
        if (line.trim() === '') return <div key={i} className="h-1" />
        return (
          <p key={i} dangerouslySetInnerHTML={{ __html: boldInline(line) }} />
        )
      })}
    </div>
  )
}

function boldInline(text: string): string {
  return text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}
