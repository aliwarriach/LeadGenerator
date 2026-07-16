import { useQuery } from '@tanstack/react-query'
import { getChatHistory } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

export function useChatHistory(leadId) {
  return useQuery({
    queryKey: ['chat-history', leadId],
    queryFn: async () => {
      const response = await getChatHistory(leadId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load chat history'))
      }
      return response.data.messages
    },
    enabled: Boolean(leadId),
  })
}
