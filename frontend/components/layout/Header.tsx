'use client'

import { usePathname } from 'next/navigation'
import { Bell, ChevronRight } from 'lucide-react'
import { getStoredUser } from '@/lib/utils'

function getBreadcrumb(pathname: string): string[] {
  const parts = pathname.split('/').filter(Boolean)
  return parts.map((part) => {
    if (part === 'dashboard') return 'Dashboard'
    if (part === 'plans') return 'Plans'
    if (part === 'investments') return 'Investments'
    if (part === 'benchmarks') return 'Benchmarks'
    if (part === 'settings') return 'Settings'
    if (part === 'new') return 'New'
    if (part === 'upload') return 'Upload'
    if (part === 'variance') return 'Variance'
    // UUID-like
    if (part.length === 36 && part.includes('-')) return '...'
    return part
  })
}

export function Header() {
  const pathname = usePathname()
  const breadcrumb = getBreadcrumb(pathname)
  const user = getStoredUser()

  return (
    <header className="h-14 bg-white border-b border-gray-100 flex items-center px-6 gap-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1 text-sm text-gray-500 flex-1">
        {breadcrumb.map((crumb, i) => (
          <div key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight className="w-3 h-3 text-gray-300" />}
            <span className={i === breadcrumb.length - 1 ? 'text-brand-primary font-medium' : ''}>
              {crumb}
            </span>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-50 text-gray-400 hover:text-gray-600 transition-colors">
          <Bell className="w-4 h-4" />
        </button>
        {user && (
          <div className="w-8 h-8 bg-brand-accent rounded-full flex items-center justify-center">
            <span className="text-white text-xs font-semibold">
              {user.name?.charAt(0)?.toUpperCase() || 'U'}
            </span>
          </div>
        )}
      </div>
    </header>
  )
}
