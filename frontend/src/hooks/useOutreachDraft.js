import { useQuery } from '@tanstack/react-query'
import { getOutreachDraft } from '../services/outreachService'
import { getErrorMessage } from '../services/api'

// 404 means "no draft ever saved for this lead+type" — a normal empty state,
// not an error. Resolves to null instead of rejecting so callers don't need
// to special-case it in isError/error handling.
export function useOutreachDraft(leadId, type) {
  return useQuery({
    queryKey: ['outreach-draft', leadId, type],
    queryFn: async () => {
      const response = await getOutreachDraft(leadId, type)
      if (response.status === 404) return null
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load saved draft'))
      }
      return response.data
    },
    enabled: Boolean(leadId && type),
  })
}
