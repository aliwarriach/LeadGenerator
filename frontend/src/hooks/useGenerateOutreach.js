import { useMutation } from '@tanstack/react-query'
import { generateEmail, generateWhatsapp, generateProposal } from '../services/outreachService'
import { getErrorMessage } from '../services/api'

const GENERATORS = {
  email: generateEmail,
  whatsapp: generateWhatsapp,
  proposal: generateProposal,
}

// Ephemeral live Groq call (a few seconds) — never persisted, callers save
// the result explicitly via useSaveOutreachDraft if the user wants to keep it.
export function useGenerateOutreach() {
  return useMutation({
    mutationFn: async ({ leadId, type, tone }) => {
      const generate = GENERATORS[type]
      const response = await generate(leadId, tone)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to generate outreach content'))
      }
      return response.data
    },
  })
}
