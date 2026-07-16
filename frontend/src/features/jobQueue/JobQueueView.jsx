import { useMemo, useState } from 'react'
import { RefreshCw } from 'lucide-react'
import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Chip from '../../components/ui/Chip'
import Pagination from '../../components/ui/Pagination'
import JobDetailModal from './JobDetailModal'
import { useJobQueue } from '../../hooks/useJobQueue'
import { useViewStore } from '../../store/useViewStore'
import { statusMeta, STATUS_OPTIONS } from '../../utils/statusMeta'
import { sourceMeta, SOURCE_OPTIONS } from '../../utils/sourceMeta'

const PAGE_SIZE = 20
const HEADERS = ['Job', 'Source', 'City', 'Status', 'Progress', 'Actions']

export default function JobQueueView() {
  const [status, setStatus] = useState('')
  const [source, setSource] = useState('')
  const [runId, setRunId] = useState('')
  const [page, setPage] = useState(1)
  const [selectedJobId, setSelectedJobId] = useState(null)
  const setView = useViewStore((s) => s.setView)

  const params = useMemo(
    () => ({
      ...(status ? { status } : {}),
      ...(source ? { source } : {}),
      ...(runId.trim() ? { run_id: runId.trim() } : {}),
      page,
      page_size: PAGE_SIZE,
    }),
    [status, source, runId, page]
  )

  const { data, isLoading, isError, error, refetch, isFetching } = useJobQueue(params)
  const hasFilters = Boolean(status || source || runId)

  function updateFilter(setter, value) {
    setter(value)
    setPage(1)
  }

  function clearFilters() {
    setStatus('')
    setSource('')
    setRunId('')
    setPage(1)
  }

  return (
    <section>
      <PageHeader
        breadcrumb="Discovery"
        title="Job Queue & Diagnostics"
        subtitle={data ? `${data.total} jobs` : 'Loading…'}
        actions={
          <Button variant="ghost" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={`h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
            Force refresh
          </Button>
        }
      />

      <Card className="mb-4 flex flex-wrap items-end gap-4 p-4">
        <div className="flex flex-col gap-1">
          <label htmlFor="statusFilter" className="text-[10.5px] font-semibold uppercase tracking-wider text-txt-dim">
            Status
          </label>
          <select
            id="statusFilter"
            value={status}
            onChange={(e) => updateFilter(setStatus, e.target.value)}
            className="rounded-lg border border-line bg-ink-soft px-2.5 py-1.5 text-[12.5px] text-txt outline-none focus:border-signal"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {statusMeta(s).label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="sourceFilter" className="text-[10.5px] font-semibold uppercase tracking-wider text-txt-dim">
            Source
          </label>
          <select
            id="sourceFilter"
            value={source}
            onChange={(e) => updateFilter(setSource, e.target.value)}
            className="rounded-lg border border-line bg-ink-soft px-2.5 py-1.5 text-[12.5px] text-txt outline-none focus:border-signal"
          >
            <option value="">All sources</option>
            {SOURCE_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {sourceMeta(s).label}
              </option>
            ))}
          </select>
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="runIdFilter" className="text-[10.5px] font-semibold uppercase tracking-wider text-txt-dim">
            Run ID
          </label>
          <input
            id="runIdFilter"
            value={runId}
            onChange={(e) => updateFilter(setRunId, e.target.value)}
            placeholder="Filter by parent run…"
            className="w-56 rounded-lg border border-line bg-ink-soft px-2.5 py-1.5 text-[12.5px] text-txt outline-none focus:border-signal"
          />
        </div>
        {hasFilters && (
          <button type="button" onClick={clearFilters} className="ml-auto text-[11.5px] text-txt-dim hover:text-txt">
            Clear filters
          </button>
        )}
      </Card>

      <Card>
        {isLoading ? (
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">Loading job queue…</p>
        ) : isError ? (
          <div className="px-5 py-10 text-center text-[13px]">
            <p className="mb-3 text-red">{error.message}</p>
            <Button variant="ghost" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        ) : data.items.length === 0 ? (
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">No jobs match these filters.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[800px] border-collapse text-[13px]">
              <thead>
                <tr>
                  {HEADERS.map((h) => (
                    <th
                      key={h}
                      className={`border-b border-line px-3.5 py-3 text-left text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute ${
                        h === 'Actions' ? 'text-right' : ''
                      }`}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((job) => {
                  const { label, tone } = statusMeta(job.status)
                  const { label: sourceLabel, icon: SourceIcon } = sourceMeta(job.source)
                  return (
                    <tr key={job.id} className="border-b border-line transition-colors duration-100 last:border-none hover:bg-signal/[.03]">
                      <td className="px-3.5 py-[13px] font-mono text-[12px] text-txt-dim">{job.id}</td>
                      <td className="px-3.5 py-[13px]">
                        <div className="flex items-center gap-1.5">
                          <SourceIcon className="h-3.5 w-3.5 text-signal" />
                          {sourceLabel}
                        </div>
                      </td>
                      <td className="px-3.5 py-[13px]">{job.location}</td>
                      <td className="px-3.5 py-[13px]">
                        <Chip tone={tone}>{label}</Chip>
                      </td>
                      <td className="px-3.5 py-[13px] text-[12px] text-txt-dim">
                        {job.leads_found_session} found · {job.leads_saved_session} saved
                        {job.status === 'running' && job.current_business_name && (
                          <div className="text-[11px] text-txt-mute">{job.current_business_name}</div>
                        )}
                      </td>
                      <td className="px-3.5 py-[13px] text-right">
                        <div className="flex justify-end gap-3">
                          <button className="text-[11.5px] text-txt-dim hover:text-txt" onClick={() => setSelectedJobId(job.id)}>
                            Details
                          </button>
                          <button
                            className="text-[11.5px] text-signal hover:underline"
                            onClick={() => setView('run-monitoring', 'Discovery', { runId: job.run_id })}
                          >
                            View run
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {data && data.total_pages > 1 && (
        <div className="mt-4 flex justify-end">
          <Pagination page={data.page} totalPages={data.total_pages} onPageChange={setPage} />
        </div>
      )}

      <JobDetailModal jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
    </section>
  )
}
