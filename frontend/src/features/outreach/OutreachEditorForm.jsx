import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import { contentToSections, sectionsToContent } from './proposalSections'

function wordCount(text) {
  const trimmed = text.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

export default function OutreachEditorForm({ type, subject, content, onSubjectChange, onContentChange, dirty, generating }) {
  if (generating) {
    return (
      <Card className="grid min-h-[500px] place-items-center px-5 py-5 text-[13px] text-txt-mute">
        Generating {type} content…
      </Card>
    )
  }

  if (type === 'proposal') {
    const sections = contentToSections(content)

    function handleSectionChange(index, nextText) {
      const next = sections.map((s, i) => (i === index ? { ...s, content: nextText } : s))
      onContentChange(sectionsToContent(next))
    }

    return (
      <div className="space-y-3.5">
        {dirty && <UnsavedBadge />}
        {sections.map((section, i) => (
          <Card key={section.heading} className="p-5">
            <label className="mb-1.5 block text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute">
              {section.heading}
            </label>
            <textarea
              value={section.content}
              onChange={(e) => handleSectionChange(i, e.target.value)}
              rows={4}
              className="w-full resize-y rounded-lg border border-line bg-ink-soft px-3.5 py-2.5 text-[13px] leading-relaxed text-txt outline-none focus:border-signal"
            />
          </Card>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3.5">
      {type === 'email' && (
        <Card className="p-5">
          <label className="mb-1.5 block text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute">
            Subject Line
          </label>
          <input
            type="text"
            value={subject ?? ''}
            onChange={(e) => onSubjectChange(e.target.value)}
            className="w-full rounded-lg border border-line bg-ink-soft px-3.5 py-2.5 text-[13px] text-txt outline-none focus:border-signal"
          />
        </Card>
      )}
      <Card className="relative flex min-h-[500px] flex-col p-5">
        <div className="mb-1.5 flex items-center justify-between">
          <label className="text-[10.5px] font-semibold uppercase tracking-wider text-txt-mute">
            {type === 'email' ? 'Email Body' : 'Message'}
          </label>
          {dirty && <UnsavedBadge />}
        </div>
        <textarea
          value={content}
          onChange={(e) => onContentChange(e.target.value)}
          placeholder={type === 'email' ? 'Write your outreach email here…' : 'Write your message here…'}
          className="min-h-[420px] flex-1 resize-none border-none bg-transparent text-[13px] leading-relaxed text-txt outline-none"
        />
        <div className="mt-3.5 flex items-center justify-between border-t border-line pt-3.5 font-mono text-[11.5px] text-txt-mute">
          <span>
            Word count: <span className="text-txt">{wordCount(content)}</span>
          </span>
        </div>
      </Card>
    </div>
  )
}

function UnsavedBadge() {
  return (
    <Chip tone="red" className="w-fit">
      Unsaved changes
    </Chip>
  )
}
