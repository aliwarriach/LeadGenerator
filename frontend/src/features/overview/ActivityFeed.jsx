import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { ACTIVITY_FEED } from '../../constants/overview'
import { renderRichText } from '../../utils/richText'

const TONE_BG = {
  signal: 'bg-signal-dim text-signal',
  violet: 'bg-violet-dim text-violet',
  blue: 'bg-blue-dim text-blue',
  amber: 'bg-amber-dim text-amber',
}

export default function ActivityFeed() {
  return (
    <Card>
      <div className="flex items-center justify-between px-5 pt-4">
        <h3 className="text-sm font-semibold text-white">Recent activity</h3>
        <Button variant="ghost" className="px-3 py-1.5 text-[11.5px]">
          View all
        </Button>
      </div>
      <div className="px-5 pb-3.5 pt-1.5">
        {ACTIVITY_FEED.map((a) => {
          const Icon = a.icon
          return (
            <div key={a.id} className="flex items-start gap-3 border-b border-line py-2.5 text-[12.5px] last:border-none">
              <div className={`grid h-[26px] w-[26px] shrink-0 place-items-center rounded-lg ${TONE_BG[a.tone]}`}>
                <Icon className="h-3.5 w-3.5" strokeWidth={2} />
              </div>
              <div className="text-txt-dim">{renderRichText(a.text)}</div>
              <div className="ml-auto whitespace-nowrap text-[11px] text-txt-mute">{a.time}</div>
            </div>
          )
        })}
      </div>
    </Card>
  )
}
