import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { VarianceSignal } from './types'
import { SIGNAL_COLORS, SIGNAL_BG_COLORS, SIGNAL_TEXT_COLORS } from './constants'

// ---------------------------------------------------------------------------
// Class name helper
// ---------------------------------------------------------------------------

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

export function formatCurrency(
  value: number,
  currency = 'USD',
  compact = false
): string {
  if (compact) {
    if (Math.abs(value) >= 1_000_000_000) {
      return `$${(value / 1_000_000_000).toFixed(1)}B`
    }
    if (Math.abs(value) >= 1_000_000) {
      return `$${(value / 1_000_000).toFixed(1)}M`
    }
    if (Math.abs(value) >= 1_000) {
      return `$${(value / 1_000).toFixed(0)}K`
    }
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value)
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}

export function formatNumber(value: number, decimals = 0): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

export function formatDate(date: string): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(date))
}

export function formatRelativeTime(date: string): string {
  const now = new Date()
  const then = new Date(date)
  const diffMs = now.getTime() - then.getTime()
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) return 'Today'
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
  return `${Math.floor(diffDays / 365)}y ago`
}

// ---------------------------------------------------------------------------
// Signal helpers
// ---------------------------------------------------------------------------

export function getSignalColor(signal: VarianceSignal): string {
  return SIGNAL_COLORS[signal]
}

export function getSignalBgColor(signal: VarianceSignal): string {
  return SIGNAL_BG_COLORS[signal]
}

export function getSignalTextColor(signal: VarianceSignal): string {
  return SIGNAL_TEXT_COLORS[signal]
}

export function getSignalClass(signal: VarianceSignal): string {
  const map: Record<VarianceSignal, string> = {
    GREEN: 'bg-green-100 text-green-800 border-green-200',
    YELLOW: 'bg-yellow-100 text-yellow-800 border-yellow-200',
    RED: 'bg-red-100 text-red-800 border-red-200',
  }
  return map[signal]
}

export function confidenceToSignal(confidence: number): VarianceSignal {
  if (confidence >= 0.85) return 'GREEN'
  if (confidence >= 0.65) return 'YELLOW'
  return 'RED'
}

export function confidenceToLabel(confidence: number): string {
  if (confidence >= 0.85) return 'High'
  if (confidence >= 0.65) return 'Med'
  return 'Low'
}

// ---------------------------------------------------------------------------
// Auth helpers
// ---------------------------------------------------------------------------

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('sentiocap_token')
}

export function setAuthToken(token: string): void {
  localStorage.setItem('sentiocap_token', token)
}

export function clearAuthToken(): void {
  localStorage.removeItem('sentiocap_token')
  localStorage.removeItem('sentiocap_user')
}

export function getStoredUser() {
  if (typeof window === 'undefined') return null
  const raw = localStorage.getItem('sentiocap_user')
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}
