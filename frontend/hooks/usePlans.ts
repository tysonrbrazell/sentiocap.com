import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { PlanCreate } from '@/lib/types'

export function usePlans() {
  return useQuery({
    queryKey: ['plans'],
    queryFn: () => api.plans.list(),
  })
}

export function usePlan(id: string, page = 1) {
  return useQuery({
    queryKey: ['plan', id, page],
    queryFn: () => api.plans.get(id, page),
    enabled: !!id,
  })
}

export function useCreatePlan() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: PlanCreate) => api.plans.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['plans'] }),
  })
}

export function useClassifyPlan(id: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (mode?: string) => api.plans.classify(id, mode),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['plan', id] })
    },
  })
}
