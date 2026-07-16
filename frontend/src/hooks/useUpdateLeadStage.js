import { useMutation, useQueryClient } from '@tanstack/react-query'
import { updateLeadStage } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

function moveLeadInPages(data, leadId, stage) {
  if (!data?.items) return data
  return { ...data, items: data.items.map((lead) => (lead.id === leadId ? { ...lead, pipeline_stage: stage } : lead)) }
}

export function useUpdateLeadStage() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ leadId, stage }) => {
      const response = await updateLeadStage(leadId, stage)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to move lead'))
      }
      return response.data
    },
    onMutate: async ({ leadId, stage }) => {
      await queryClient.cancelQueries({ queryKey: ['leads', 'all'] })
      const previous = queryClient.getQueryData(['leads', 'all'])
      queryClient.setQueryData(['leads', 'all'], (data) => moveLeadInPages(data, leadId, stage))
      return { previous }
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['leads', 'all'], context.previous)
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['leads', 'all'] })
      queryClient.invalidateQueries({ queryKey: ['leads'], exact: false })
    },
  })
}
