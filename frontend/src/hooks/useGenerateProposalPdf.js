import { useMutation } from '@tanstack/react-query'
import { generateProposalPdf } from '../services/outreachService'
import { getErrorMessage } from '../services/api'

function triggerDownload(blob, draftId) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `proposal-${draftId}.pdf`
  anchor.click()
  URL.revokeObjectURL(url)
}

// Only valid for saved proposal-type drafts — a 422 here means the caller
// tried to PDF an email/whatsapp draft, a dev-error, not a user-facing empty state.
export function useGenerateProposalPdf() {
  return useMutation({
    mutationFn: async (draftId) => {
      const response = await generateProposalPdf(draftId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to generate PDF'))
      }
      triggerDownload(response.data, draftId)
      return true
    },
  })
}
