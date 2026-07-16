import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import OverallScoreRing from './OverallScoreRing'
import MetricRingGrid from './MetricRingGrid'
import AuditSummaryCard from './AuditSummaryCard'
import IssuesRecommendationsGrid from './IssuesRecommendationsGrid'
import { REANALYZE_TOAST } from '../../constants/audit'
import { useToastStore } from '../../store/useToastStore'
import { useViewStore } from '../../store/useViewStore'
import { useLead } from '../../hooks/useLead'
import { useAuditLead } from '../../hooks/useAuditLead'
import { mapLeadToBusiness } from '../businesses/mapLeadToBusiness'

export default function AuditView() {
  const show = useToastStore((s) => s.show)
  const breadcrumb = useViewStore((s) => s.breadcrumb)
  const leadId = useViewStore((s) => s.params.leadId)
  const { data: lead, isLoading, isError, error, refetch } = useLead(leadId)
  const auditMutation = useAuditLead()

  if (!leadId) {
    return (
      <section>
        <PageHeader breadcrumb="Intelligence" title="Website Audit" />
        <Card className="px-5 py-10 text-center text-[13px] text-txt-mute">
          Open a business from the Businesses table and click the audit icon to view its report.
        </Card>
      </section>
    )
  }

  if (isLoading) {
    return (
      <section>
        <PageHeader breadcrumb={breadcrumb} title="Website Audit" />
        <Card className="px-5 py-10 text-center text-[13px] text-txt-mute">Loading audit…</Card>
      </section>
    )
  }

  if (isError) {
    return (
      <section>
        <PageHeader breadcrumb={breadcrumb} title="Website Audit" />
        <Card className="px-5 py-10 text-center text-[13px]">
          <p className="mb-3 text-red">{error.message}</p>
          <Button variant="ghost" onClick={() => refetch()}>
            Retry
          </Button>
        </Card>
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
          <Button
            variant="ghost"
            onClick={() => {
              auditMutation.mutate(leadId)
              show(REANALYZE_TOAST)
            }}
            disabled={isPending}
          >
            ↻ {business.audit ? 'Re-analyze' : 'Run AI Audit'}
          </Button>
        }
      />
      <div className="mb-3.5 grid grid-cols-1 gap-3.5 lg:grid-cols-[280px_1fr]">
        <Card>
          <OverallScoreRing score={business.score ?? 0} />
        </Card>
        <Card className="px-[22px] py-5">
          <h3 className="mb-1 text-[13px] font-semibold text-white">AI qualitative</h3>
          <p className="mb-3.5 text-[11px] text-txt-mute">Source: LLM analysis via Groq</p>
          {business.audit ? (
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
    </section>
  )
}
