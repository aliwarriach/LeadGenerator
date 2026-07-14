import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { listLeads } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

export function useLeads(params) {
  return useQuery({
    queryKey: ['leads', params],
    queryFn: async () => {
      const response = await listLeads(params)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load businesses'))
      }
      return response.data
    },
    placeholderData: keepPreviousData,
  })
}
