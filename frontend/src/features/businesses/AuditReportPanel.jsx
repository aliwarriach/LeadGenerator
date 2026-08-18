import Chip from '../../components/ui/Chip'
import Button from '../../components/ui/Button'
import { scoreTone } from '../../constants/businesses'

const SCORE_FIELDS = [
  { key: 'uiScore', label: 'UI' },
  { key: 'conversionScore', label: 'Conversion' },
  { key: 'contentScore', label: 'Content' },
  { key: 'trustScore', label: 'Trust' },
]

export default function AuditReportPanel({ audit, pending, error, onRetry }) {
  return (
    <div className="space-y-2.5">
      {pending && (
        <div className="flex items-center gap-2 rounded-lg border border-line bg-ink-soft px-4 py-3.5 text-[13px] text-txt-dim">
          <span className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border-2 border-txt-dim border-t-transparent" />
          Running AI audit… this can take up to 30 seconds.
        </div>
      )}
      {!pending && error && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-red/40 bg-red-dim px-4 py-3.5 text-[13px]">
          <span className="text-red">{error}</span>
          <Button variant="ghost" onClick={onRetry}>
            Try again
          </Button>
        </div>
      )}
      {audit && (
        <div className="rounded-lg border border-line bg-ink-soft px-4 py-3.5">
          <p className="mb-3 text-[11px] uppercase tracking-wide text-txt-mute">AI-generated · source: LLM analysis via Groq</p>
          <div className="mb-3 flex flex-wrap gap-2">
            {SCORE_FIELDS.map(({ key, label }) => (
              <Chip key={key} tone={scoreTone(audit[key] * 10)} className="font-mono">
                {label} {audit[key]}/10
              </Chip>
            ))}
          </div>
          {audit.issues.length > 0 && (
            <ul className="mb-3 list-inside list-disc space-y-1 text-[12.5px] text-txt-dim">
              {audit.issues.map((issue) => (
                <li key={issue}>{issue}</li>
              ))}
            </ul>
          )}
          <p className="text-[12.5px] leading-relaxed text-txt-dim">{audit.summary}</p>
        </div>
      )}
      {!pending && !error && !audit && (
        <p className="px-1 text-[12.5px] text-txt-mute">No audit yet — click "Run AI Audit" to generate one.</p>
      )}
    </div>
  )
}
