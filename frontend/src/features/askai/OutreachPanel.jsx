import { useState } from 'react'
import { Search } from 'lucide-react'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import { OUTREACH_TYPES, OUTREACH_TONES } from '../../constants/askai'
import { useViewStore } from '../../store/useViewStore'
import { useToastStore } from '../../store/useToastStore'
import { useGenerateOutreach } from '../../hooks/useGenerateOutreach'

export default function OutreachPanel({ leadId, onOpenPicker }) {
  const breadcrumb = useViewStore((s) => s.breadcrumb)
  const setView = useViewStore((s) => s.setView)
  const show = useToastStore((s) => s.show)
  const generateMutation = useGenerateOutreach()

  const [type, setType] = useState('email')
  const [tone, setTone] = useState('default')

  function handleGenerate() {
    generateMutation.mutate(
      { leadId, type, tone },
      {
        onSuccess: (data) => {
          setView('outreach-editor', breadcrumb, { leadId, type, generated: data, breadcrumb })
        },
        onError: (err) => show(err.message),
      }
    )
  }

  return (
    <Card className="px-[18px] py-[18px]">
      <h3 className="mb-1 text-[13px] font-semibold text-white">One-click outreach</h3>
      <p className="mb-3.5 text-[11.5px] text-txt-mute">Generated from profile + audit. Editable before saving.</p>

      <div className="mb-3.5">
        <div className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute">Type</div>
        {OUTREACH_TYPES.map((t) => {
          const Icon = t.icon
          const active = t.id === type
          return (
            <button
              key={t.id}
              onClick={() => setType(t.id)}
              className={`mb-2 flex w-full items-center gap-2.5 rounded-[10px] border px-3.5 py-2.5 text-left text-[12.5px] transition-colors duration-150 ${
                active ? 'border-violet text-txt' : 'border-line-hi text-txt-dim hover:border-violet hover:text-txt'
              }`}
            >
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-violet-dim">
                <Icon className="h-3.5 w-3.5 text-violet" />
              </span>
              {t.label}
            </button>
          )
        })}
      </div>

      <div className="mb-3.5">
        <div className="mb-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute">Tone</div>
        <div className="flex flex-wrap gap-1.5">
          {OUTREACH_TONES.map((t) => (
            <button
              key={t.id}
              onClick={() => setTone(t.id)}
              className={`rounded-full border px-3 py-1.5 text-[11.5px] font-medium transition-colors duration-150 ${
                tone === t.id ? 'border-signal text-signal' : 'border-line-hi text-txt-dim hover:text-txt'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <Button onClick={handleGenerate} disabled={!leadId || generateMutation.isPending} className="w-full justify-center">
        {generateMutation.isPending ? 'Generating…' : 'Generate'}
      </Button>
      {!leadId && (
        <div className="mt-2.5 text-center">
          <p className="mb-1.5 text-[11px] text-txt-mute">No business selected yet.</p>
          <Button variant="ghost" onClick={onOpenPicker} className="w-full justify-center text-[11.5px]">
            <Search className="h-3 w-3" /> Choose a business
          </Button>
        </div>
      )}
    </Card>
  )
}
