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

      // The singular ['lead', id] query (AuditView, Ask AI) is a different
      // cache key from the plural ['leads'] list queries above — TanStack's
      // prefix matching does not treat one as a match for the other, so
      // without this the screen showing this exact mutation's result never
      // sees it update.
      queryClient.setQueryData(['lead', audit.lead_id], (lead) => (lead ? mergeAuditIntoLead(lead, audit) : lead))
      queryClient.invalidateQueries({ queryKey: ['lead', audit.lead_id] })
    },
  })
}
