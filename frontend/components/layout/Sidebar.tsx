'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Settings, LogOut, Waves, FileText, TrendingUp } from 'lucide-react'
import { cn, clearAuthToken, getStoredUser } from '@/lib/utils'

// ---------------------------------------------------------------------------
// Agent nav items
// ---------------------------------------------------------------------------

const AGENT_ITEMS = [
  { href: '/agents', label: 'Home', emoji: '🏠', exactMatch: true },
] as const

const NAMED_AGENTS = [
  { href: '/agents/scout', label: 'Scout', emoji: '🔍', desc: 'Classification' },
  { href: '/agents/sentinel', label: 'Sentinel', emoji: '🎯', desc: 'Signals & Decisions' },
  { href: '/agents/compass', label: 'Compass', emoji: '📊', desc: 'Benchmarks' },
  { href: '/agents/oracle', label: 'Oracle', emoji: '📈', desc: 'Forecasting' },
  { href: '/agents/scribe', label: 'Scribe', emoji: '📝', desc: 'Reports' },
  { href: '/agents/sage', label: 'Sage', emoji: '💬', desc: 'Ask Anything' },
  { href: '/agents/strategist', label: 'Strategist', emoji: '🔮', desc: 'Scenarios' },
  { href: '/agents/guardian', label: 'Guardian', emoji: '🛡️', desc: 'Compliance' },
] as const

const LEGACY_ITEMS = [
  { href: '/plans', label: 'Plans', icon: FileText },
  { href: '/investments', label: 'Investments', icon: TrendingUp },
] as const

// Placeholder status — in production, fetch from /api/agent/status per-agent
// green = active/healthy, yellow = needs attention, red = signal fired
const AGENT_STATUS: Record<string, 'green' | 'yellow' | 'red'> = {
  '/agents/scout': 'green',
  '/agents/sentinel': 'yellow',
  '/agents/compass': 'green',
  '/agents/oracle': 'green',
  '/agents/scribe': 'green',
  '/agents/sage': 'green',
  '/agents/strategist': 'green',
  '/agents/guardian': 'green',
}

const STATUS_DOT: Record<'green' | 'yellow' | 'red', string> = {
  green: 'bg-green-400',
  yellow: 'bg-yellow-400',
  red: 'bg-red-500 animate-pulse',
}

export function Sidebar() {
  const pathname = usePathname()
  const router = useRouter()
  const user = getStoredUser()

  function handleLogout() {
    clearAuthToken()
    router.push('/login')
  }

  function isActive(href: string, exact = false) {
    if (exact) return pathname === href
    return pathname === href || pathname.startsWith(href + '/')
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
            <div className="text-xs text-gray-400">Agent Intelligence</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 overflow-y-auto space-y-4">
        {/* Home */}
        <div className="space-y-0.5">
          {AGENT_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                isActive(item.href, item.exactMatch)
                  ? 'bg-brand-accent-light text-brand-accent'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-brand-primary'
              )}
            >
              <span className="w-4 text-center">{item.emoji}</span>
              {item.label}
            </Link>
          ))}
        </div>

        {/* Divider + Agents */}
        <div>
          <p className="px-3 mb-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
            Agents
          </p>
          <div className="space-y-0.5">
            {NAMED_AGENTS.map((agent) => {
              const active = isActive(agent.href)
              const statusColor = AGENT_STATUS[agent.href] ?? 'green'
              return (
                <Link
                  key={agent.href}
                  href={agent.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group',
                    active
                      ? 'bg-brand-accent-light text-brand-accent'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-brand-primary'
                  )}
                >
                  <span className="w-4 text-center text-base">{agent.emoji}</span>
                  <span className="flex-1">{agent.label}</span>
                  {/* Status dot */}
                  <span
                    className={cn('w-1.5 h-1.5 rounded-full shrink-0', STATUS_DOT[statusColor])}
                    title={agent.desc}
                  />
                </Link>
              )
            })}
          </div>
        </div>

        {/* Divider + Legacy */}
        <div>
          <p className="px-3 mb-1.5 text-[10px] font-semibold text-gray-400 uppercase tracking-widest">
            Legacy
          </p>
          <div className="space-y-0.5">
            {LEGACY_ITEMS.map((item) => {
              const Icon = item.icon
              const active = isActive(item.href)
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                    active
                      ? 'bg-brand-accent-light text-brand-accent'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-brand-primary'
                  )}
                >
                  <Icon className={cn('w-4 h-4', active ? 'text-brand-accent' : 'text-gray-400')} />
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>

        {/* Settings */}
        <div className="space-y-0.5">
          <Link
            href="/settings"
            className={cn(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive('/settings')
                ? 'bg-brand-accent-light text-brand-accent'
                : 'text-gray-600 hover:bg-gray-50 hover:text-brand-primary'
            )}
          >
            <Settings className={cn('w-4 h-4', isActive('/settings') ? 'text-brand-accent' : 'text-gray-400')} />
            Settings
          </Link>
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
