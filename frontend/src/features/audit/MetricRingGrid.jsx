import RadialProgress from '../../components/charts/RadialProgress'

function toneColor(value) {
  if (value >= 75) return '#3ecf8e'
  if (value >= 55) return '#f0b429'
  return '#f0616d'
}

export default function MetricRingGrid({ metrics, color }) {
  return (
    <div className="grid grid-cols-2 gap-3.5 sm:grid-cols-4">
      {metrics.map((m) => (
        <div key={m.label} className="flex flex-col items-center gap-2">
          <RadialProgress value={m.value} size={76} strokeWidth={7} color={color ?? toneColor(m.value)}>
            <span className="font-mono text-base font-medium text-white">{m.value}</span>
          </RadialProgress>
          <span className="text-[11.5px] text-txt-dim">{m.label}</span>
        </div>
      ))}
    </div>
  )
}
