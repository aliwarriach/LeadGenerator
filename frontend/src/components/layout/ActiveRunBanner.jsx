import { Loader2 } from 'lucide-react'
import { useActiveRunStore } from '../../store/useActiveRunStore'
import { useViewStore } from '../../store/useViewStore'
import { useDiscoveryRun } from '../../hooks/useDiscoveryRun'
import { statusMeta } from '../../utils/statusMeta'

// Mounted once at the app shell level (not per-view) so an in-progress run
// stays reachable no matter where the user navigates to.
export default function ActiveRunBanner() {
  const activeRunId = useActiveRunStore((s) => s.activeRunId)
  const setView = useViewStore((s) => s.setView)
  const { data: run } = useDiscoveryRun(activeRunId)

  if (!activeRunId || !run) return null

  const doneJobs = run.jobs.filter((job) => job.status !== 'pending' && job.status !== 'running').length

  return (
    <button
      type="button"
      onClick={() => setView('run-monitoring', 'Discovery', { runId: activeRunId })}
      className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-signal/30 bg-signal-dim px-3 py-2 text-left text-[12px] font-medium text-signal transition-colors hover:border-signal"
    >
      <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" />
      <span className="min-w-0 flex-1 truncate">
        Discovery {statusMeta(run.status).label.toLowerCase()} — {doneJobs}/{run.jobs.length} jobs
      </span>
    </button>
  )
}
