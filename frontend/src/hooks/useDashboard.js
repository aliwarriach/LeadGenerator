import { useQuery } from '@tanstack/react-query'
import { getDashboardStats, getDiscoveryVolume, getLeadStageMix, getRecentActivity } from '../services/dashboardService'
import { getErrorMessage } from '../services/api'

const REFRESH_MS = 30_000

export function useDashboardStats() {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      const response = await getDashboardStats()
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load dashboard stats'))
      }
      return response.data
    },
    refetchInterval: REFRESH_MS,
  })
}

export function useDiscoveryVolume(days = 7) {
  return useQuery({
    queryKey: ['dashboard', 'discovery-volume', days],
    queryFn: async () => {
      const response = await getDiscoveryVolume(days)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load discovery volume'))
      }
      return response.data
    },
    refetchInterval: REFRESH_MS,
  })
}

export function useLeadStageMix() {
  return useQuery({
    queryKey: ['dashboard', 'lead-stage-mix'],
    queryFn: async () => {
      const response = await getLeadStageMix()
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load lead stage mix'))
      }
      return response.data
    },
    refetchInterval: REFRESH_MS,
  })
}

export function useRecentActivity(limit = 10) {
  return useQuery({
    queryKey: ['dashboard', 'activity', limit],
    queryFn: async () => {
      const response = await getRecentActivity(limit)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load recent activity'))
      }
      return response.data
    },
    refetchInterval: REFRESH_MS,
  })
}
