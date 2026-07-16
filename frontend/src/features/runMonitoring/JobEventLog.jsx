import { useJobEvents } from '../../hooks/useJobEvents'

export default function JobEventLog({ jobId, enabled }) {
  const { data, isLoading, isError, error } = useJobEvents(jobId, { enabled })

  return (
    <div className="rounded-lg border border-line bg-ink-soft p-3">
      <p className="mb-2 text-[10.5px] uppercase tracking-wider text-txt-mute">Live log</p>
      <div className="max-h-40 space-y-1 overflow-y-auto font-mono text-[11.5px] text-txt-dim">
        {isLoading && <p>Loading log…</p>}
        {isError && <p className="text-red">{error.message}</p>}
        {!isLoading && !isError && data.items.length === 0 && <p className="text-txt-mute">No events yet.</p>}
        {data?.items.map((event) => (
          <p key={event.id}>
            <span className="text-txt-mute">[{new Date(event.created_at).toLocaleTimeString()}]</span> {event.message}
          </p>
        ))}
      </div>
    </div>
  )
}
