import Card from '../../components/ui/Card'
import { Sparkles } from 'lucide-react'

export default function ToneTabs({ tones, activeTone, onSelect, pending }) {
  return (
    <Card className="mb-3.5 flex items-center gap-2 overflow-x-auto px-2 py-2">
      {tones.map((t) => {
        const active = t.id === activeTone
        return (
          <button
            key={t.id}
            disabled={pending}
            onClick={() => onSelect(t.id)}
            className={`whitespace-nowrap rounded-lg px-3.5 py-2 text-[11.5px] font-semibold uppercase tracking-wide transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-60 ${
              active ? 'border-b-2 border-signal text-signal' : 'text-txt-mute hover:text-txt'
            }`}
          >
            {t.label}
          </button>
        )
      })}
      <div className="ml-auto flex items-center gap-1.5 pr-2 text-[10px] uppercase text-txt-mute">
        <Sparkles className="h-3.5 w-3.5" />
        {pending ? 'Generating…' : 'AI-generated'}
      </div>
    </Card>
  )
}
