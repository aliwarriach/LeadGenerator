import { formatDistanceToNow, parseISO } from 'date-fns'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { useRecentActivity } from '../../hooks/useDashboard'
import { useViewStore } from '../../store/useViewStore'
import { ACTIVITY_TYPE_META } from '../../constants/overview'
import { renderRichText } from '../../utils/richText'

const TONE_BG = {
  signal: 'bg-signal-dim text-signal',
  violet: 'bg-violet-dim text-violet',
  blue: 'bg-blue-dim text-blue',
  amber: 'bg-amber-dim text-amber',
}

function describeActivity(activity) {
  const meta = ACTIVITY_TYPE_META[activity.type]
  if (!meta?.label) return `**${activity.lead_name}** — ${activity.description}`
  return `**${activity.lead_name}** ${meta.label} — ${activity.description}`
}

export default function ActivityFeed() {
  const setView = useViewStore((s) => s.setView)
  const { data, isLoading, isError, error, refetch } = useRecentActivity(10)

  // Every activity type reads/writes through the same lead-scoped panel
  // (chat + outreach), so one consistent destination beats branching per
  // type — Ask AI works for every lead regardless of website presence,
  // unlike Audit which has no useful content for website-less leads.
  function openActivity(activity) {
    setView('askai', `Overview / ${activity.lead_name}`, { leadId: activity.lead_id })
  }

  return (
    <Card>
      <div className="flex items-center justify-between px-5 pt-4">
        <h3 className="text-sm font-semibold text-white">Recent activity</h3>
      </div>
      <div className="px-5 pb-3.5 pt-1.5">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="flex items-start gap-3 border-b border-line py-2.5 last:border-none">
              <div className="h-[26px] w-[26px] shrink-0 animate-pulse rounded-lg bg-line" />
              <div className="h-3 flex-1 animate-pulse rounded bg-line" />
            </div>
          ))
        ) : isError ? (
          <div className="py-10 text-center text-[13px]">
            <p className="mb-3 text-red">{error.message}</p>
            <Button variant="ghost" onClick={() => refetch()}>
              Retry
            </Button>
          </div>
        ) : data.items.length === 0 ? (
          <p className="py-10 text-center text-[13px] text-txt-mute">No activity yet.</p>
        ) : (
          data.items.map((a) => {
            const meta = ACTIVITY_TYPE_META[a.type] ?? ACTIVITY_TYPE_META.stage_change
            const Icon = meta.icon
            return (
              <button
                key={a.id}
                type="button"
                onClick={() => openActivity(a)}
                title={`Open ${a.lead_name} in Ask AI`}
                className="flex w-full items-start gap-3 border-b border-line py-2.5 text-left text-[12.5px] transition-colors duration-100 last:border-none hover:bg-signal/[.03]"
              >
                <div className={`grid h-[26px] w-[26px] shrink-0 place-items-center rounded-lg ${TONE_BG[meta.tone]}`}>
                  <Icon className="h-3.5 w-3.5" strokeWidth={2} />
                </div>
                <div className="text-txt-dim">{renderRichText(describeActivity(a))}</div>
                <div className="ml-auto whitespace-nowrap text-[11px] text-txt-mute">
                  {formatDistanceToNow(parseISO(a.created_at), { addSuffix: true })}
                </div>
              </button>
            )
          })
        )}
      </div>
    </Card>
  )
}
