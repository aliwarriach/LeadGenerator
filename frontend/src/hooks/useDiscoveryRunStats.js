import { useQuery } from '@tanstack/react-query'
import { getDiscoveryRunStats } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

export function useDiscoveryRunStats() {
  return useQuery({
    queryKey: ['discovery-run-stats'],
    queryFn: async () => {
      const response = await getDiscoveryRunStats()
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load run stats'))
      }
      return response.data
    },
  })
}
