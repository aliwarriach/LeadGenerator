import { useMutation, useQueryClient } from '@tanstack/react-query'
import { sendChatMessage } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

// Live Groq call (a few seconds) — appends both turns to the cached history
// on success so the panel doesn't need a refetch to show the reply.
export function useSendChatMessage(leadId) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (message) => {
      const response = await sendChatMessage(leadId, message)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to send message'))
      }
      return response.data
    },
    onMutate: async (message) => {
      queryClient.setQueryData(['chat-history', leadId], (messages) => [
        ...(messages ?? []),
        { role: 'user', content: message, created_at: new Date().toISOString() },
      ])
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['chat-history', leadId], (messages) => [
        ...(messages ?? []),
        { role: 'assistant', content: data.reply, created_at: data.created_at },
      ])
    },
  })
}
