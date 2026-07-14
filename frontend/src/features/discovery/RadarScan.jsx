const RINGS = [110, 190, 270]
const BLIPS = [
  { left: '38%', bottom: 34, delay: '0s' },
  { left: '60%', bottom: 58, delay: '.8s' },
  { left: '48%', bottom: 20, delay: '1.7s' },
]

export default function RadarScan() {
  return (
    <div
      aria-hidden="true"
      className="relative my-1 h-[112px] overflow-hidden rounded-[10px] border border-line"
      style={{ background: 'radial-gradient(circle at 50% 120%, rgba(62,207,142,.12), transparent 65%)' }}
    >
      {RINGS.map((size) => (
        <span
          key={size}
          className="absolute bottom-[-40px] left-1/2 -translate-x-1/2 rounded-full border border-[rgba(62,207,142,.18)]"
          style={{ width: size, height: size }}
        />
      ))}
      <span
        className="absolute bottom-[-40px] left-1/2 h-[150px] w-[150px] origin-top-left animate-sweep"
        style={{ background: 'conic-gradient(from 0deg, rgba(62,207,142,.25), transparent 40deg)' }}
      />
      {BLIPS.map((b) => (
        <span
          key={b.left + b.bottom}
          className="absolute h-1.5 w-1.5 animate-blip rounded-full bg-signal shadow-[0_0_8px_#3ecf8e]"
          style={{ left: b.left, bottom: b.bottom, animationDelay: b.delay }}
        />
      ))}
    </div>
  )
}
