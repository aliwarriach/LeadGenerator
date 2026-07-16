import RadialProgress from '../../components/charts/RadialProgress'

function toneColor(value, max) {
  const pct = (value / max) * 100
  if (pct >= 75) return '#3ecf8e'
  if (pct >= 55) return '#f0b429'
  return '#f0616d'
}

export default function MetricRingGrid({ metrics, max = 100, color }) {
  return (
    <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
      {metrics.map((m) => (
        <div key={m.label} className="flex flex-col items-center gap-2">
          <RadialProgress value={m.value} max={max} size={76} strokeWidth={7} color={color ?? toneColor(m.value, max)}>
            <span className="font-mono text-base font-medium text-white">{m.value}</span>
          </RadialProgress>
          <span className="text-[11.5px] text-txt-dim">{m.label}</span>
        </div>
      ))}
    </div>
  )
}
