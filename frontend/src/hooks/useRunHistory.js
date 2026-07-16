import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { listDiscoveryRuns } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

// Lightweight list, no jobs/counts embedded — a slow background refetch while
// the screen is open is enough, no tight polling needed.
const BACKGROUND_POLL_MS = 10000

export function useRunHistory(params) {
  return useQuery({
    queryKey: ['discovery-runs', params],
    queryFn: async () => {
      const response = await listDiscoveryRuns(params)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load run history'))
      }
      return response.data
    },
    placeholderData: keepPreviousData,
    refetchInterval: BACKGROUND_POLL_MS,
  })
}
