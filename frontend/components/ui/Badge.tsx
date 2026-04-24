import { cn } from '@/lib/utils'
import type { VarianceSignal } from '@/lib/types'

type BadgeVariant = 'default' | 'rtb' | 'ctb' | 'signal-green' | 'signal-yellow' | 'signal-red' | 'outline' | 'blue' | 'purple' | 'emerald' | 'gray'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  signal?: VarianceSignal
  className?: string
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  default: 'bg-gray-100 text-gray-700',
  rtb: 'bg-blue-100 text-blue-800',
  ctb: 'bg-emerald-100 text-emerald-800',
  'signal-green': 'bg-green-100 text-green-800',
  'signal-yellow': 'bg-yellow-100 text-yellow-800',
  'signal-red': 'bg-red-100 text-red-800',
  outline: 'bg-transparent border border-gray-300 text-gray-700',
  blue: 'bg-blue-100 text-blue-800',
  purple: 'bg-purple-100 text-purple-800',
  emerald: 'bg-emerald-100 text-emerald-800',
  gray: 'bg-gray-100 text-gray-700',
}

export function Badge({ children, variant = 'default', signal, className }: BadgeProps) {
  let cls = VARIANT_CLASSES[variant]
  if (signal) {
    const signalMap: Record<VarianceSignal, string> = {
      GREEN: VARIANT_CLASSES['signal-green'],
      YELLOW: VARIANT_CLASSES['signal-yellow'],
      RED: VARIANT_CLASSES['signal-red'],
    }
    cls = signalMap[signal]
  }

  return (
    <span className={cn('inline-flex items-center px-2 py-0.5 rounded text-xs font-medium', cls, className)}>
      {children}
    </span>
  )
}

export function SignalDot({ signal }: { signal: VarianceSignal }) {
  const colors: Record<VarianceSignal, string> = {
    GREEN: 'bg-green-500',
    YELLOW: 'bg-yellow-500',
    RED: 'bg-red-500',
  }
  return (
    <span className={cn('inline-block w-2 h-2 rounded-full', colors[signal])} />
  )
}
