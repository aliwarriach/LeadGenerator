import { Search } from 'lucide-react'
import { NAV_SECTIONS, WORKSPACE_USER } from '../../constants/navigation'
import { useViewStore } from '../../store/useViewStore'
import ActiveRunBanner from './ActiveRunBanner'

export default function Sidebar() {
  const view = useViewStore((s) => s.view)
  const setView = useViewStore((s) => s.setView)

  return (
    <aside className="sticky top-0 flex h-screen w-[228px] shrink-0 flex-col border-r border-line bg-ink-soft">
      <div className="flex items-center gap-2.5 px-5 pb-4 pt-5">
        <div className="grid h-[30px] w-[30px] place-items-center rounded-lg bg-signal-dim">
          <Search className="h-[18px] w-[18px] text-signal" strokeWidth={2.2} />
        </div>
        <div className="font-display text-[17px] font-bold tracking-tight text-white">
          Lead<span className="text-signal">Gen</span>
        </div>
      </div>
      <ActiveRunBanner />
      <nav className="flex-1 px-3 py-1.5">
        {NAV_SECTIONS.map((section) => (
          <div key={section.label}>
            <div className="px-2.5 pb-1.5 pt-3.5 text-[10px] font-medium uppercase tracking-widest text-txt-mute">
              {section.label}
            </div>
            {section.items.map((item) => {
              const Icon = item.icon
              const active = view === item.id
              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`mb-0.5 flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-[13.5px] font-medium transition-colors duration-150 ${
                    active ? 'bg-signal-dim text-signal' : 'text-txt-dim hover:bg-ink-card hover:text-txt'
                  }`}
                >
                  <Icon className="h-4 w-4 shrink-0" strokeWidth={2} />
                  {item.label}
                </button>
              )
            })}
          </div>
        ))}
      </nav>
      <div className="border-t border-line px-5 py-3.5">
        <div className="text-[13px] text-txt">{WORKSPACE_USER.name}</div>
        <div className="text-[11.5px] text-txt-mute">{WORKSPACE_USER.org}</div>
      </div>
    </aside>
  )
}
