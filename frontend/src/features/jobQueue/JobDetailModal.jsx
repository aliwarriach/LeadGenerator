import Modal from '../../components/ui/Modal'
import Chip from '../../components/ui/Chip'
import { useJob } from '../../hooks/useJob'
import { statusMeta } from '../../utils/statusMeta'
import { sourceMeta } from '../../utils/sourceMeta'

export default function JobDetailModal({ jobId, onClose }) {
  const { data: job, isLoading, isError, error } = useJob(jobId)

  return (
    <Modal open={Boolean(jobId)} onClose={onClose} title="Job detail">
      {isLoading && <p className="text-[13px] text-txt-mute">Loading job…</p>}
      {isError && <p className="text-[13px] text-red">{error.message}</p>}
      {job && (
        <div className="space-y-4 text-[13px]">
          <div className="flex items-center justify-between">
            <span className="font-mono text-txt-dim">{job.id}</span>
            <Chip tone={statusMeta(job.status).tone}>{statusMeta(job.status).label}</Chip>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Source</p>
              <p className="text-txt">{sourceMeta(job.source).label}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Location</p>
              <p className="text-txt">{job.location}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Found this session</p>
              <p className="font-mono text-txt">{job.leads_found_session}</p>
            </div>
            <div>
              <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">Saved this session</p>
              <p className="font-mono text-signal">{job.leads_saved_session}</p>
            </div>
            <div className="col-span-2">
              <p className="text-[10.5px] uppercase tracking-wider text-txt-mute">All-time total for this source</p>
              <p className="font-mono text-txt">{job.total_leads_scraped_by_source ?? '—'}</p>
            </div>
          </div>
          {job.error_message && <p className="text-red">{job.error_message}</p>}
        </div>
      )}
    </Modal>
  )
}
