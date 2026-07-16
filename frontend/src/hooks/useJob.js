import { useQuery } from '@tanstack/react-query'
import { getJob } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

// The standalone job resource — the only place total_leads_scraped_by_source
// is populated (all-time count for that source, not scoped to one run).
export function useJob(jobId) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: async () => {
      const response = await getJob(jobId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load job'))
      }
      return response.data
    },
    enabled: Boolean(jobId),
  })
}
