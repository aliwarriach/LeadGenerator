import { useMutation, useQueryClient } from '@tanstack/react-query'
import { saveOutreachDraft, updateOutreachDraft } from '../services/outreachService'
import { getErrorMessage } from '../services/api'

// Saves a new draft (POST) or updates an existing one (PATCH) depending on
// whether a draftId is already known — one mutation for both since the
// editor doesn't otherwise distinguish "first save" from "edit + resave".
export function useSaveOutreachDraft() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ leadId, type, draftId, subject, content }) => {
      const response = draftId
        ? await updateOutreachDraft(draftId, { subject, content })
        : await saveOutreachDraft(leadId, type, { subject, content })
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to save draft'))
      }
      return response.data
    },
    onSuccess: (draft) => {
      queryClient.setQueryData(['outreach-draft', draft.lead_id, draft.type], draft)
    },
  })
}
