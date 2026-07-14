import { BarChart3, Sparkles, Mail, Plus, Lightbulb } from 'lucide-react'
import Chip from '../../components/ui/Chip'
import { scoreTone } from '../../constants/businesses'
import { useViewStore } from '../../store/useViewStore'
import { useToastStore } from '../../store/useToastStore'

const HEADERS = ['Business', 'Rating', 'Website', 'Score', 'Actions']
const ACTION_BTN =
  'grid h-[29px] w-[29px] shrink-0 place-items-center rounded-lg border border-line-hi text-txt-dim transition-colors duration-150 hover:border-signal hover:text-signal'

export default function BusinessTable({ businesses }) {
  const setView = useViewStore((s) => s.setView)
  const show = useToastStore((s) => s.show)

  if (businesses.length === 0) {
    return <p className="px-5 py-10 text-center text-[13px] text-txt-mute">No businesses match these filters.</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-[13px]">
        <thead>
          <tr>
            {HEADERS.map((h) => (
              <th
                key={h}
                className={`border-b border-line px-3.5 py-3 text-left text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute ${
                  h === 'Actions' ? 'text-right' : ''
                }`}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {businesses.map((b) => (
            <tr key={b.id} className="border-b border-line transition-colors duration-100 last:border-none hover:bg-signal/[.03]">
              <td className="px-3.5 py-[13px]">
                <div className="font-semibold text-white">{b.name}</div>
                <div className="text-[11.5px] text-txt-mute">{b.category}</div>
              </td>
              <td className="px-3.5 py-[13px]">
                {b.rating != null ? (
                  <>
                    <span className="text-[12px] text-amber">★</span>{' '}
                    <span className="font-mono">{b.rating}</span>
                  </>
                ) : (
                  <span className="text-txt-mute">—</span>
                )}
              </td>
              <td className="px-3.5 py-[13px]">
                {b.website ? (
                  <span className="font-mono text-[12px] text-blue">{b.website}</span>
                ) : (
                  <Chip tone="amber">No website</Chip>
                )}
              </td>
              <td className="px-3.5 py-[13px]">
                {b.score != null ? (
                  <Chip tone={scoreTone(b.score)} className="font-mono text-[12px]">
                    {b.score}
                  </Chip>
                ) : (
                  <span className="text-txt-mute">—</span>
                )}
              </td>
              <td className="px-3.5 py-[13px]">
                <div className="flex justify-end gap-1.5">
                  {b.website ? (
                    <button title="View audit" onClick={() => setView('audit')} className={ACTION_BTN}>
                      <BarChart3 className="h-3.5 w-3.5" />
                    </button>
                  ) : (
                    <button
                      title="Opportunity pitch"
                      onClick={() => show('**No-website recommendation** generated — suggested: landing page + booking')}
                      className={ACTION_BTN}
                    >
                      <Lightbulb className="h-3.5 w-3.5" />
                    </button>
                  )}
                  <button title="Ask AI" onClick={() => setView('askai')} className={ACTION_BTN}>
                    <Sparkles className="h-3.5 w-3.5" />
                  </button>
                  <button title="Generate outreach" onClick={() => show(`**Cold email** drafted for ${b.name}`)} className={ACTION_BTN}>
                    <Mail className="h-3.5 w-3.5" />
                  </button>
                  <button title="Save lead" onClick={() => show(`**${b.name}** added to pipeline`)} className={ACTION_BTN}>
                    <Plus className="h-3.5 w-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
