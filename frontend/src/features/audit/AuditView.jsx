import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Chip from '../../components/ui/Chip'
import OverallScoreRing from './OverallScoreRing'
import MetricRingGrid from './MetricRingGrid'
import AuditSummaryCard from './AuditSummaryCard'
import IssuesRecommendationsGrid from './IssuesRecommendationsGrid'
import {
  AUDIT_SUBJECT,
  LIGHTHOUSE_METRICS,
  LIGHTHOUSE_SOURCE,
  AI_METRICS,
  AI_METRICS_SOURCE,
  REANALYZE_TOAST,
  EXPORT_PDF_TOAST,
} from '../../constants/audit'
import { useToastStore } from '../../store/useToastStore'

export default function AuditView() {
  const show = useToastStore((s) => s.show)

  return (
    <section>
      <PageHeader
        breadcrumb={AUDIT_SUBJECT.breadcrumb}
        title="Website Audit"
        titleExtra={
          <Chip tone="muted" className="align-middle font-mono">
            {AUDIT_SUBJECT.version}
          </Chip>
        }
        subtitle={AUDIT_SUBJECT.domain}
        subtitleMono
        actions={
          <>
            <Button variant="ghost" onClick={() => show(REANALYZE_TOAST)}>
              ↻ Re-analyze
            </Button>
            <Button onClick={() => show(EXPORT_PDF_TOAST)}>↓ Export PDF</Button>
          </>
        }
      />
      <div className="mb-3.5 grid grid-cols-1 gap-3.5 lg:grid-cols-[280px_1fr]">
        <Card>
          <OverallScoreRing />
        </Card>
        <Card className="px-[22px] py-5">
          <h3 className="mb-1 text-[13px] font-semibold text-white">Hard metrics</h3>
          <p className="mb-3.5 text-[11px] text-txt-mute">{LIGHTHOUSE_SOURCE}</p>
          <MetricRingGrid metrics={LIGHTHOUSE_METRICS} />
          <hr className="my-[18px] border-line border-dashed" />
          <h3 className="mb-1 text-[13px] font-semibold text-white">AI qualitative</h3>
          <p className="mb-3.5 text-[11px] text-txt-mute">{AI_METRICS_SOURCE}</p>
          <MetricRingGrid metrics={AI_METRICS} color="#a78bfa" />
        </Card>
      </div>
      <AuditSummaryCard />
      <IssuesRecommendationsGrid />
    </section>
  )
}
