import { useMutation, useQueryClient } from '@tanstack/react-query'
import { stopDiscoveryRun } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

// Cooperative stop — the response reflects stop_requested: true on
// non-terminal jobs, but nothing is confirmed stopped until the next poll.
export function useStopRun(runId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async () => {
      const response = await stopDiscoveryRun(runId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to stop run'))
      }
      return response.data
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['discovery-run', runId] })
    },
  })
}
