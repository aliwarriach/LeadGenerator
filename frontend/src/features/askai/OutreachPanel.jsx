import Card from '../../components/ui/Card'
import { OUTREACH_ACTIONS, GROUNDING_CONTEXT } from '../../constants/askai'
import { useToastStore } from '../../store/useToastStore'

export default function OutreachPanel() {
  const show = useToastStore((s) => s.show)

  return (
    <Card className="px-[18px] py-[18px]">
      <h3 className="mb-1 text-[13px] font-semibold text-white">One-click outreach</h3>
      <p className="mb-3.5 text-[11.5px] text-txt-mute">Generated from profile + audit. Saved to Outreach Assets.</p>
      {OUTREACH_ACTIONS.map((a) => {
        const Icon = a.icon
        return (
          <button
            key={a.id}
            onClick={() => show(a.toast)}
            className="mb-2 flex w-full items-center gap-2.5 rounded-[10px] border border-line-hi px-3.5 py-2.5 text-left text-[12.5px] text-txt-dim transition-colors duration-150 hover:border-violet hover:text-txt"
          >
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-violet-dim">
              <Icon className="h-3.5 w-3.5 text-violet" />
            </span>
            {a.label}
          </button>
        )
      })}
      <div className="mt-4 rounded-[10px] border border-line bg-ink-soft px-3.5 py-3 text-[11.5px] leading-relaxed text-txt-mute">
        <b className="text-txt-dim">Grounding context</b>
        <br />
        {GROUNDING_CONTEXT}
      </div>
    </Card>
  )
}
