import { useMutation, useQueryClient } from '@tanstack/react-query'
import { stopDiscoveryJob } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

// Cooperative stop, same semantics as useStopRun. runId is optional — Job
// Queue rows may not have a loaded parent-run query to invalidate.
export function useStopJob(runId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (jobId) => {
      const response = await stopDiscoveryJob(jobId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to stop job'))
      }
      return response.data
    },
    onSettled: () => {
      if (runId) queryClient.invalidateQueries({ queryKey: ['discovery-run', runId] })
      queryClient.invalidateQueries({ queryKey: ['discovery-jobs'] })
    },
  })
}
