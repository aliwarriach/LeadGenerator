import { useState } from 'react'
import { ChevronDown, ChevronUp, Loader2 } from 'lucide-react'
import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import Button from '../../components/ui/Button'
import JobEventLog from './JobEventLog'
import { statusMeta, isTerminalStatus } from '../../utils/statusMeta'
import { sourceMeta } from '../../utils/sourceMeta'
import { useStopJob } from '../../hooks/useStopJob'
import { useCountdown } from '../../hooks/useCountdown'
import { useToastStore } from '../../store/useToastStore'

export default function JobCard({ job, runId }) {
  const [expanded, setExpanded] = useState(false)
  const stopJob = useStopJob(runId)
  const show = useToastStore((s) => s.show)
  const { label: statusLabel, tone } = statusMeta(job.status)
  const { label: sourceLabel, icon: SourceIcon } = sourceMeta(job.source)
  const countdown = useCountdown(job.error_retry_after_seconds)
  const terminal = isTerminalStatus(job.status)
  const stopping = stopJob.isPending && stopJob.variables === job.id
  const stopDisabled = terminal || job.stop_requested || stopping

  function handleStop() {
    stopJob.mutate(job.id, {
      onError: (err) => show(`**Failed to stop job** — ${err.message}`),
    })
  }

  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line-hi bg-ink-soft">
            <SourceIcon className="h-4 w-4 text-signal" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white">{sourceLabel}</h3>
            <p className="text-[11.5px] text-txt-mute">
              {job.location} · {job.query}
            </p>
          </div>
        </div>
        <Chip tone={tone}>{statusLabel}</Chip>
      </div>

      <div className="grid grid-cols-3 gap-3 border-y border-line/60 py-3 text-center">
        <div>
          <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Found</p>
          <p className="font-mono text-base text-white">{job.leads_found_session}</p>
        </div>
        <div>
          <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Saved</p>
          <p className="font-mono text-base text-signal">{job.leads_saved_session}</p>
        </div>
        <div>
          <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Failures</p>
          <p className="font-mono text-base text-red">{job.extraction_failures_session}</p>
        </div>
      </div>

      {job.status === 'running' && job.current_business_name && (
        <p className="flex items-center gap-1.5 text-[11.5px] text-txt-dim">
          <Loader2 className="h-3 w-3 animate-spin text-signal" />
          Currently scraping: <span className="text-txt">{job.current_business_name}</span>
        </p>
      )}

      {job.error_message && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-red/30 bg-red-dim px-3 py-2.5">
          <p className="text-[12px] text-red">{job.error_message}</p>
          {countdown != null && countdown > 0 && (
            <p className="shrink-0 font-mono text-xs text-txt-dim">Retry in {countdown}s</p>
          )}
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => setExpanded((e) => !e)}
          className="flex items-center gap-1 text-[11.5px] text-txt-dim hover:text-txt"
        >
          {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {expanded ? 'Hide log' : 'View log'}
        </button>
        <Button
          variant="danger"
          className={`px-3 py-1.5 text-xs ${stopDisabled ? 'cursor-not-allowed opacity-50' : ''}`}
          disabled={stopDisabled}
          onClick={handleStop}
        >
          {stopping ? 'Stopping…' : job.stop_requested && !terminal ? 'Stop requested' : 'Stop job'}
        </Button>
      </div>

      {expanded && <JobEventLog jobId={job.id} enabled={expanded} />}
    </Card>
  )
}
