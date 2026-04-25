'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import {
  LayoutDashboard,
  FileText,
  TrendingUp,
  BarChart3,
  Settings,
  LogOut,
  Waves,
  Target,
  Bot,
  BookOpen,
} from 'lucide-react'
import { cn, clearAuthToken, getStoredUser } from '@/lib/utils'

const NAV_ITEMS = [
  { href: '/agent', label: 'Agent', icon: Bot },
  { href: '/decisions', label: 'Decisions', icon: Target },
  { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/plans', label: 'Plans', icon: FileText },
  { href: '/investments', label: 'Investments', icon: TrendingUp },
  { href: '/benchmarks', label: 'Benchmarks', icon: BarChart3 },
  { href: '/documents', label: 'Documents', icon: BookOpen },
  { href: '/settings', label: 'Settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const user = getStoredUser()

  function handleLogout() {
    clearAuthToken()
    router.push('/login')
  }

  return (
    <aside className="fixed left-0 top-0 h-full w-[240px] bg-white border-r border-gray-100 flex flex-col z-30">
      {/* Logo */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-brand-accent rounded-lg flex items-center justify-center">
            <Waves className="w-4 h-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-brand-primary">SentioCap</div>
            <div className="text-xs text-gray-400">Expense Intelligence</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 overflow-y-auto">
        <div className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/')
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-accent-light text-brand-accent'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-brand-primary'
                )}
              >
                <Icon className={cn('w-4 h-4', isActive ? 'text-brand-accent' : 'text-gray-400')} />
                {item.label}
              </Link>
            )
          })}
        </div>
      </nav>

      {/* User info & logout */}
      <div className="p-3 border-t border-gray-100">
        {user && (
          <div className="px-3 py-2 mb-1">
            <div className="text-xs font-medium text-brand-primary truncate">{user.name}</div>
            <div className="text-xs text-gray-400 truncate">{user.email}</div>
          </div>
        )}
        <button
          onClick={handleLogout}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-500 hover:bg-gray-50 hover:text-red-600 transition-colors w-full"
        >
          <LogOut className="w-4 h-4" />
          Sign out
        </button>
      </div>
    </aside>
  )
}
