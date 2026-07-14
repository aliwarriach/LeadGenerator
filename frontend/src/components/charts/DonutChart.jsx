export default function DonutChart({ data, centerValue, centerLabel, size = 120 }) {
  const total = data.reduce((sum, d) => sum + d.count, 0)
  const radius = 46
  const circumference = 2 * Math.PI * radius
  let offset = 0

  return (
    <svg width={size} height={size} viewBox="0 0 120 120">
      {data.map((d) => {
        const len = (d.count / total) * circumference
        const segment = (
          <circle
            key={d.stage}
            cx="60"
            cy="60"
            r={radius}
            fill="none"
            stroke={d.color}
            strokeWidth="14"
            strokeDasharray={`${len - 2} ${circumference - len + 2}`}
            strokeDashoffset={-offset}
            transform="rotate(-90 60 60)"
          />
        )
        offset += len
        return segment
      })}
      <text x="60" y="57" textAnchor="middle" fontFamily="Space Grotesk" fontSize="21" fontWeight="700" fill="#fff">
        {centerValue}
      </text>
      <text x="60" y="74" textAnchor="middle" fontSize="9.5" fill="#5c6b7d">
        {centerLabel}
      </text>
    </svg>
  )
}
