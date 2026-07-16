import { useState } from 'react'
import { formatDistanceToNow } from 'date-fns'
import PageHeader from '../../components/ui/PageHeader'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import Chip from '../../components/ui/Chip'
import Pagination from '../../components/ui/Pagination'
import { useRunHistory } from '../../hooks/useRunHistory'
import { useViewStore } from '../../store/useViewStore'
import { statusMeta } from '../../utils/statusMeta'

const PAGE_SIZE = 20
const HEADERS = ['Run', 'Created', 'Status']

export default function RunHistoryView() {
  const [page, setPage] = useState(1)
  const setView = useViewStore((s) => s.setView)
  const { data, isLoading, isError, error, refetch } = useRunHistory({ page, page_size: PAGE_SIZE })

  function openRun(runId) {
    setView('run-monitoring', 'Discovery', { runId })
  }

  return (
    <section>
      <PageHeader breadcrumb="Discovery" title="Run History" subtitle={data ? `${data.total} total runs` : 'Loading…'} />
      <Card>
        {isLoading ? (
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">Loading run history…</p>
        ) : isError ? (
          <div className="px-5 py-10 text-center text-[13px]">
            <p className="mb-3 text-red">{error.message}</p>
            <Button variant="ghost" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        ) : data.items.length === 0 ? (
          <p className="px-5 py-10 text-center text-[13px] text-txt-mute">No discovery runs yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse text-[13px]">
              <thead>
                <tr>
                  {HEADERS.map((h) => (
                    <th
                      key={h}
                      className="border-b border-line px-3.5 py-3 text-left text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((run) => {
                  const { label, tone } = statusMeta(run.status)
                  return (
                    <tr
                      key={run.id}
                      onClick={() => openRun(run.id)}
                      className="cursor-pointer border-b border-line transition-colors duration-100 last:border-none hover:bg-signal/[.03]"
                    >
                      <td className="px-3.5 py-[13px]">
                        <div className="font-semibold text-white">{run.custom_niche}</div>
                        <div className="text-[11.5px] text-txt-mute">
                          {run.city}, {run.country}
                        </div>
                      </td>
                      <td className="px-3.5 py-[13px] font-mono text-[12px] text-txt-dim">
                        {formatDistanceToNow(new Date(run.created_at), { addSuffix: true })}
                      </td>
                      <td className="px-3.5 py-[13px]">
                        <Chip tone={tone}>{label}</Chip>
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
    </section>
  )
}
