import { formatDistanceToNow } from 'date-fns'
import { StopCircle, AlertTriangle } from 'lucide-react'
import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Chip from '../../components/ui/Chip'
import JobCard from './JobCard'
import { useViewStore } from '../../store/useViewStore'
import { useToastStore } from '../../store/useToastStore'
import { useDiscoveryRun } from '../../hooks/useDiscoveryRun'
import { useStopRun } from '../../hooks/useStopRun'
import { statusMeta, isTerminalStatus } from '../../utils/statusMeta'

export default function RunMonitoringView() {
  const runId = useViewStore((s) => s.params.runId)
  const setView = useViewStore((s) => s.setView)

  if (!runId) {
    return (
      <section>
        <PageHeader breadcrumb="Discovery" title="Run Monitoring" subtitle="No run selected." />
        <Card className="px-5 py-10 text-center text-[13px] text-txt-mute">
          Pick a run from{' '}
          <button className="text-signal underline" onClick={() => setView('run-history', 'Discovery')}>
            Run History
          </button>{' '}
          to monitor it here.
        </Card>
      </section>
    )
  }

  return <RunMonitoringContent runId={runId} />
}

function RunMonitoringContent({ runId }) {
  const show = useToastStore((s) => s.show)
  const { data: run, isLoading, isError, error, refetch } = useDiscoveryRun(runId)
  const stopRun = useStopRun(runId)

  if (isLoading) {
    return (
      <section>
        <PageHeader breadcrumb="Discovery" title="Run Monitoring" subtitle="Loading run…" />
      </section>
    )
  }

  if (isError) {
    return (
      <section>
        <PageHeader breadcrumb="Discovery" title="Run Monitoring" subtitle="Unable to load this run." />
        <Card className="px-5 py-10 text-center text-[13px]">
          <p className="mb-3 text-red">{error.message}</p>
          <Button variant="ghost" onClick={() => refetch()}>
            Retry
          </Button>
        </Card>
      </section>
    )
  }

  const { label: statusLabel, tone } = statusMeta(run.status)
  const terminal = isTerminalStatus(run.status)
  const stopDisabled = terminal || stopRun.isPending

  function handleStopRun() {
    stopRun.mutate(undefined, {
      onSuccess: () => show('**Stop requested** — waiting for jobs to acknowledge'),
      onError: (err) => show(`**Failed to stop run** — ${err.message}`),
    })
  }

  return (
    <section>
      <PageHeader
        breadcrumb="Discovery"
        title={`Discovery Run: ${run.custom_niche} in ${run.city}`}
        subtitle={
          run.started_at
            ? `Started ${formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}`
            : 'Not started yet'
        }
        actions={
          <Button
            variant="danger"
            className={stopDisabled ? 'cursor-not-allowed opacity-50' : ''}
            disabled={stopDisabled}
            onClick={handleStopRun}
          >
            <StopCircle className="h-4 w-4" />
            {stopRun.isPending ? 'Stopping…' : 'Stop entire run'}
          </Button>
        }
      />

      <div className="mb-6 flex items-center gap-2">
        <Chip tone={tone}>{statusLabel}</Chip>
      </div>

      {run.warnings.length > 0 && (
        <div className="mb-6 space-y-2">
          {run.warnings.map((warning, i) => (
            <div key={i} className="flex items-start gap-3 rounded-lg border border-red/30 bg-red-dim px-4 py-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-red" />
              <p className="text-[12.5px] text-txt">
                <span className="font-semibold text-red">{warning.source}:</span> {warning.message}
              </p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {run.jobs.map((job) => (
          <JobCard key={job.id} job={job} runId={runId} />
        ))}
      </div>
    </section>
  )
}
