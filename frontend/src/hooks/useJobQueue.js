import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { listDiscoveryJobs } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

// No single derived status to gate a polling cadence on (unlike a single
// run) — on-demand fetch + the screen's "Force refresh" button is enough.
export function useJobQueue(params) {
  return useQuery({
    queryKey: ['discovery-jobs', params],
    queryFn: async () => {
      const response = await listDiscoveryJobs(params)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load job queue'))
      }
      return response.data
    },
    placeholderData: keepPreviousData,
  })
}
