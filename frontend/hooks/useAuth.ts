import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { getStoredUser, getAuthToken } from '@/lib/utils'

export function useAuth() {
  const hasToken = !!getAuthToken()

  const { data: user, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: () => api.auth.me(),
    enabled: hasToken,
    staleTime: 5 * 60 * 1000,
  })

  return {
    user: user ?? getStoredUser(),
    isLoading: hasToken ? isLoading : false,
    isAuthenticated: !!user || !!getStoredUser(),
  }
}
