import { BUSINESS_FILTERS } from '../../constants/businesses'

export default function BusinessFilters({ active, onSelect }) {
  return (
    <>
      {BUSINESS_FILTERS.map((f) => {
        const on = f.id === active
        return (
          <button
            key={f.id}
            type="button"
            onClick={() => onSelect(f.id)}
            aria-pressed={on}
            className={`rounded-lg border px-3.5 py-1.5 text-[12.5px] transition-colors duration-150 ${
              on ? 'border-signal bg-signal-dim font-semibold text-signal' : 'border-line-hi text-txt-dim hover:text-txt'
            }`}
          >
            {f.label} {f.count !== undefined && <span className="font-mono">{f.count}</span>}
          </button>
        )
      })}
    </>
  )
}
