export default function RadialProgress({
  value,
  max = 100,
  size = 76,
  strokeWidth = 7,
  color,
  trackColor = '#28323e',
  className = '',
  children,
}) {
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (Math.min(value, max) / max) * circumference
  const center = size / 2

  return (
    <div className={`relative inline-grid place-items-center ${className}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={center} cy={center} r={radius} fill="none" stroke={trackColor} strokeWidth={strokeWidth} />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${center} ${center})`}
          className="transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>
      {children && <div className="absolute inset-0 grid place-items-center">{children}</div>}
    </div>
  )
}
