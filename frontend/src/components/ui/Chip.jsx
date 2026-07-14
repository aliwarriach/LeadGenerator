const TONES = {
  signal: 'bg-signal-dim text-signal',
  amber: 'bg-amber-dim text-amber',
  red: 'bg-red-dim text-red',
  blue: 'bg-blue-dim text-blue',
  violet: 'bg-violet-dim text-violet',
  muted: 'bg-txt-dim/10 text-txt-dim',
}

export default function Chip({ tone = 'muted', children, className = '' }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${TONES[tone]} ${className}`}>
      {children}
    </span>
  )
}
