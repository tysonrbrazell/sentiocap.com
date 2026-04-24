import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { InvestmentCreate } from '@/lib/types'

export function useInvestments() {
  return useQuery({
    queryKey: ['investments'],
    queryFn: () => api.investments.list(),
  })
}

export function useInvestment(id: string) {
  return useQuery({
    queryKey: ['investment', id],
    queryFn: () => api.investments.get(id),
    enabled: !!id,
  })
}

export function useCreateInvestment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: InvestmentCreate) => api.investments.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['investments'] }),
  })
}
