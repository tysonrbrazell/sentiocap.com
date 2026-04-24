import { cn } from '@/lib/utils'

interface TableProps {
  children?: React.ReactNode
  className?: string
  colSpan?: number
}

export function Table({ children, className, colSpan: _c }: TableProps) {
  return (
    <div className="overflow-x-auto">
      <table className={cn('w-full text-sm', className)}>{children}</table>
    </div>
  )
}

export function Thead({ children, className, colSpan: _c }: TableProps) {
  return (
    <thead className={cn('border-b border-gray-100', className)}>{children}</thead>
  )
}

export function Tbody({ children, className, colSpan: _c }: TableProps) {
  return <tbody className={cn('divide-y divide-gray-50', className)}>{children}</tbody>
}

export function Tr({ children, className, colSpan: _c, onClick }: TableProps & { onClick?: () => void }) {
  return (
    <tr
      className={cn(
        'transition-colors',
        onClick && 'cursor-pointer hover:bg-gray-50',
        className
      )}
      onClick={onClick}
    >
      {children}
    </tr>
  )
}

export function Th({ children, className, colSpan }: TableProps) {
  return (
    <th colSpan={colSpan} className={cn('px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wide whitespace-nowrap', className)}>
      {children}
    </th>
  )
}

export function Td({ children, className, colSpan }: TableProps) {
  return (
    <td colSpan={colSpan} className={cn('px-4 py-3 text-sm text-gray-700', className)}>
      {children}
    </td>
  )
}
