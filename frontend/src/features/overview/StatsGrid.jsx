import Card from '../../components/ui/Card'
import { STATS } from '../../constants/overview'

const VALUE_TONE = { amber: 'text-amber' }
const DELTA_TONE = { signal: 'text-signal' }

export default function StatsGrid() {
  return (
    <div className="mb-[22px] grid grid-cols-2 gap-3.5 lg:grid-cols-4">
      {STATS.map((s) => (
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
