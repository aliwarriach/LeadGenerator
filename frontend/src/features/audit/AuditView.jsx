import { useEffect, useState } from 'react'
import { ArrowLeftRight } from 'lucide-react'
import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import BusinessPickerModal from '../../components/business/BusinessPickerModal'
import OverallScoreRing from './OverallScoreRing'
import MetricRingGrid from './MetricRingGrid'
import AuditSummaryCard from './AuditSummaryCard'
import IssuesRecommendationsGrid from './IssuesRecommendationsGrid'
import { REANALYZE_TOAST, AUDIT_COMPLETE_TOAST } from '../../constants/audit'
import { useToastStore } from '../../store/useToastStore'
import { useViewStore } from '../../store/useViewStore'
import { useSelectedLeadStore } from '../../store/useSelectedLeadStore'
import { useLead } from '../../hooks/useLead'
import { useAuditLead } from '../../hooks/useAuditLead'
import { mapLeadToBusiness } from '../businesses/mapLeadToBusiness'

export default function AuditView() {
  const show = useToastStore((s) => s.show)
  const breadcrumb = useViewStore((s) => s.breadcrumb)
  const setView = useViewStore((s) => s.setView)
  const paramLeadId = useViewStore((s) => s.params.leadId)
  const selectedLeadId = useSelectedLeadStore((s) => s.selectedLeadId)
  const setSelectedLeadId = useSelectedLeadStore((s) => s.setSelectedLeadId)
  const leadId = paramLeadId ?? selectedLeadId
  const { data: lead, isLoading, isError, error, refetch } = useLead(leadId)
  const auditMutation = useAuditLead()
  const [pickerOpen, setPickerOpen] = useState(false)

  // Keeps the "last selected lead" fallback in sync with an explicit URL/nav
  // param (e.g. a direct link with ?leadId=… or a fresh pick from Businesses).
  useEffect(() => {
    if (paramLeadId) setSelectedLeadId(paramLeadId)
  }, [paramLeadId, setSelectedLeadId])

  // Same navigation mechanism used app-wide for a lead-scoped tab switch —
  // mirrors Ask AI's picker wiring exactly (see AskAIView.handleSelectBusiness).
  function handleSelectBusiness(newLeadId) {
    setView('audit', 'Workspace', { leadId: newLeadId })
    setPickerOpen(false)
  }

  function handleRunAudit() {
    show(REANALYZE_TOAST)
    auditMutation.mutate(leadId, {
      onSuccess: () => show(AUDIT_COMPLETE_TOAST),
      onError: (err) => show(err.message),
    })
  }

  // The picker must be reachable no matter what state the screen is in
  // (nothing selected yet, loading, errored, or loaded) — it's the primary
  // way in now, not just a fallback for when a lead is already picked.
  const switcherAction = (
    <Button variant="ghost" onClick={() => setPickerOpen(true)}>
      <ArrowLeftRight className="h-3.5 w-3.5" /> {leadId ? 'Switch business' : 'Pick a business'}
    </Button>
  )
  const picker = (
    <BusinessPickerModal
      open={pickerOpen}
      onClose={() => setPickerOpen(false)}
      activeLeadId={leadId}
      onSelect={handleSelectBusiness}
    />
  )

  if (!leadId) {
    return (
      <section>
        <PageHeader breadcrumb="Intelligence" title="Website Audit" actions={switcherAction} />
        <Card className="px-5 py-10 text-center text-[13px] text-txt-mute">
          Pick a business above, or open one from the Businesses table's audit icon.
        </Card>
        {picker}
      </section>
    )
  }

  if (isLoading) {
    return (
      <section>
        <PageHeader breadcrumb={breadcrumb} title="Website Audit" actions={switcherAction} />
        <Card className="px-5 py-10 text-center text-[13px] text-txt-mute">Loading audit…</Card>
        {picker}
      </section>
    )
  }

  if (isError) {
    return (
      <section>
        <PageHeader breadcrumb={breadcrumb} title="Website Audit" actions={switcherAction} />
        <Card className="px-5 py-10 text-center text-[13px]">
          <p className="mb-3 text-red">{error.message}</p>
          <Button variant="ghost" onClick={() => refetch()}>
            Retry
          </Button>
        </Card>
        {picker}
      </section>
    )
  }

  const business = mapLeadToBusiness(lead)
  const isPending = auditMutation.isPending
  const isAuditError = auditMutation.isError

  return (
    <section>
      <PageHeader
        breadcrumb={breadcrumb}
        title="Website Audit"
        subtitle={business.website ?? business.name}
        subtitleMono={Boolean(business.website)}
        actions={
          <>
            {switcherAction}
            {business.hasWebsite && (
              <Button variant="ghost" onClick={handleRunAudit} disabled={isPending}>
                ↻ {business.audit ? 'Re-analyze' : 'Run AI Audit'}
              </Button>
            )}
          </>
        }
      />
      <div className="mb-3.5 grid grid-cols-1 gap-3.5 lg:grid-cols-[280px_1fr]">
        <Card>
          <OverallScoreRing score={business.score} hasWebsite={business.hasWebsite} />
        </Card>
        <Card className="px-[22px] py-5">
          <h3 className="mb-1 text-[13px] font-semibold text-white">AI qualitative</h3>
          <p className="mb-3.5 text-[11px] text-txt-mute">Source: LLM analysis via Groq</p>
          {!business.hasWebsite ? (
            // The backend audit endpoint hard-rejects a website-less lead
            // (LeadHasNoWebsiteError -> 422) — surface that honestly up front
            // instead of letting "Run AI Audit" fire into a guaranteed error.
            <div className="flex flex-col items-start gap-3">
              <p className="text-[12.5px] text-txt-mute">
                {business.name} has no website on file, so there's nothing for the AI audit to analyze.
              </p>
              <Button variant="ghost" onClick={() => setView('askai', breadcrumb, { leadId: business.id })}>
                Ask AI about this business instead
              </Button>
            </div>
          ) : business.audit ? (
            <MetricRingGrid
              metrics={[
                { label: 'UI / UX', value: business.audit.uiScore },
                { label: 'Conversion', value: business.audit.conversionScore },
                { label: 'Content', value: business.audit.contentScore },
                { label: 'Trust signals', value: business.audit.trustScore },
              ]}
              max={10}
              color="#a78bfa"
            />
          ) : isPending ? (
            <p className="text-[12.5px] text-txt-mute">Running AI audit… this can take up to 30 seconds.</p>
          ) : (
            <p className="text-[12.5px] text-txt-mute">
              {isAuditError ? auditMutation.error.message : 'No audit yet — click "Run AI Audit" to generate one.'}
            </p>
          )}
        </Card>
      </div>
      {business.audit && (
        <>
          <AuditSummaryCard summary={business.audit.summary} />
          {business.audit.issues.length > 0 && <IssuesRecommendationsGrid issues={business.audit.issues} />}
        </>
      )}
      {picker}
    </section>
  )
}
