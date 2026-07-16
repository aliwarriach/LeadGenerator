import { useQuery } from '@tanstack/react-query'
import { getLead } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

export function useLead(leadId) {
  return useQuery({
    queryKey: ['lead', leadId],
    queryFn: async () => {
      const response = await getLead(leadId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load business'))
      }
      return response.data
    },
    enabled: Boolean(leadId),
  })
}
