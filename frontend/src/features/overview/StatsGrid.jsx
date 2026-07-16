import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { useDashboardStats } from '../../hooks/useDashboard'

function statCards(stats) {
  return [
    {
      key: 'discovered',
      label: 'Businesses discovered',
      value: stats.discovered_total.toLocaleString(),
      delta: `▲ ${stats.discovered_this_week.toLocaleString()} this week`,
      deltaTone: 'signal',
    },
    {
      key: 'hot',
      label: 'No website — hot leads',
      value: stats.no_website_total.toLocaleString(),
      valueTone: 'amber',
      delta: `${stats.no_website_pct}% of total`,
      deltaTone: 'muted',
    },
    {
      key: 'audits',
      label: 'Audits completed',
      value: stats.audits_completed_total.toLocaleString(),
      delta: `▲ ${stats.audits_completed_this_week.toLocaleString()} this week`,
      deltaTone: 'signal',
    },
    {
      key: 'deals',
      label: 'Active deals',
      value: stats.active_deals.toLocaleString(),
      delta: 'Contacted, qualified & proposal stages',
      deltaTone: 'muted',
    },
  ]
}

const VALUE_TONE = { amber: 'text-amber' }
const DELTA_TONE = { signal: 'text-signal' }

function SkeletonGrid() {
  return (
    <div className="mb-[22px] grid grid-cols-2 gap-3.5 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="px-5 py-[18px]">
          <div className="h-3 w-24 animate-pulse rounded bg-line" />
          <div className="mt-2.5 h-7 w-16 animate-pulse rounded bg-line" />
          <div className="mt-2 h-3 w-20 animate-pulse rounded bg-line" />
        </Card>
      ))}
    </div>
  )
}

export default function StatsGrid() {
  const { data, isLoading, isError, error, refetch } = useDashboardStats()

  if (isLoading) return <SkeletonGrid />

  if (isError) {
    return (
      <Card className="mb-[22px] px-5 py-6 text-center text-[13px]">
        <p className="mb-3 text-red">{error.message}</p>
        <Button variant="ghost" onClick={() => refetch()}>
          Retry
        </Button>
      </Card>
    )
  }

  return (
    <div className="mb-[22px] grid grid-cols-2 gap-3.5 lg:grid-cols-4">
      {statCards(data).map((s) => (
        <Card key={s.key} className="px-5 py-[18px]">
          <div className="text-[11.5px] font-medium text-txt-mute">{s.label}</div>
          <div className={`mt-1.5 font-display text-[28px] font-bold tracking-tight ${VALUE_TONE[s.valueTone] ?? 'text-white'}`}>
            {s.value}
          </div>
          <div className={`mt-1 text-[11.5px] ${DELTA_TONE[s.deltaTone] ?? 'text-txt-mute'}`}>{s.delta}</div>
        </Card>
      ))}
    </div>
  )
}
