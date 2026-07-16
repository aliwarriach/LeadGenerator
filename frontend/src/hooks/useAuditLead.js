import { useMutation, useQueryClient } from '@tanstack/react-query'
import { runAudit } from '../services/leadsService'
import { getErrorMessage } from '../services/api'

// Merges the audit response's ai_* fields onto the matching lead wherever it's
// cached (list pages) so "already audited" state is consistent everywhere the
// lead is rendered, without needing a refetch.
function mergeAuditIntoLead(lead, audit) {
  if (lead.id !== audit.lead_id) return lead
  return {
    ...lead,
    ai_ui_score: audit.ui_score,
    ai_conversion_score: audit.conversion_score,
    ai_content_score: audit.content_score,
    ai_trust_score: audit.trust_score,
    ai_issues: audit.issues,
    ai_summary: audit.summary,
    ai_audited_at: new Date().toISOString(),
  }
}

export function useAuditLead() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (leadId) => {
      const response = await runAudit(leadId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to run AI audit'))
      }
      return response.data
    },
    onSuccess: (audit) => {
      queryClient.setQueriesData({ queryKey: ['leads'] }, (data) => {
        if (!data?.items) return data
        return { ...data, items: data.items.map((lead) => mergeAuditIntoLead(lead, audit)) }
      })
      queryClient.invalidateQueries({ queryKey: ['leads'] })
    },
  })
}
