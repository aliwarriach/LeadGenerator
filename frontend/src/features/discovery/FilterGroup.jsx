export default function FilterGroup({ label, options, selected, onToggle, getLabel = (o) => o.label, getId = (o) => o.id }) {
  return (
    <div className="px-[22px] pb-[18px]">
      <label className="mb-2 block text-[11.5px] font-semibold uppercase tracking-wider text-txt-dim">{label}</label>
      <div className="flex flex-wrap gap-1.5">
        {options.map((opt) => {
          const id = getId(opt)
          const on = selected.includes(id)
          return (
            <button
              key={id}
              type="button"
              onClick={() => onToggle(id)}
              aria-pressed={on}
              className={`rounded-full border px-[13px] py-1.5 text-[12.5px] transition-colors duration-150 ${
                on
                  ? 'border-signal bg-signal-dim font-semibold text-signal'
                  : 'border-line-hi text-txt-dim hover:border-txt-mute hover:text-txt'
              }`}
            >
              {getLabel(opt)}
            </button>
          )
        })}
      </div>
    </div>
  )
}
