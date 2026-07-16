import { useEffect, useState } from 'react'
import { ArrowLeft } from 'lucide-react'
import Chip from '../../components/ui/Chip'
import { useViewStore } from '../../store/useViewStore'
import { useToastStore } from '../../store/useToastStore'
import { useLead } from '../../hooks/useLead'
import { useOutreachDraft } from '../../hooks/useOutreachDraft'
import { useGenerateOutreach } from '../../hooks/useGenerateOutreach'
import { useSaveOutreachDraft } from '../../hooks/useSaveOutreachDraft'
import { OUTREACH_TYPES, OUTREACH_TONES } from '../../constants/askai'
import { sectionsToContent, contentToSections } from './proposalSections'
import ToneTabs from './ToneTabs'
import OutreachEditorForm from './OutreachEditorForm'
import OutreachToolbar from './OutreachToolbar'

const TYPE_LABELS = Object.fromEntries(OUTREACH_TYPES.map((t) => [t.id, t.label]))

// Normalizes each generation response shape (email/whatsapp/proposal) into
// the one { subject, content } model the editor and draft-save endpoint share.
function fromGenerated(type, data) {
  if (type === 'email') return { subject: data.subject, content: data.email_body }
  if (type === 'whatsapp') return { subject: null, content: data.message }
  return { subject: null, content: sectionsToContent(data.sections) }
}

export default function OutreachEditorView() {
  const params = useViewStore((s) => s.params)
  const setView = useViewStore((s) => s.setView)
  const show = useToastStore((s) => s.show)
  const { leadId, type, generated } = params

  const leadQuery = useLead(leadId)
  const draftQuery = useOutreachDraft(leadId, type)
  const generateMutation = useGenerateOutreach()
  const saveMutation = useSaveOutreachDraft()

  const [tone, setTone] = useState('default')
  const [subject, setSubject] = useState(null)
  const [content, setContent] = useState('')
  const [draftId, setDraftId] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [hydrated, setHydrated] = useState(false)

  // Priority on first load: content handed in from OutreachPanel's generate
  // action, else the last saved draft (once it resolves), else stay empty.
  useEffect(() => {
    if (hydrated) return
    if (generated) {
      const normalized = fromGenerated(type, generated)
      setSubject(normalized.subject)
      setContent(normalized.content)
      setHydrated(true)
      return
    }
    if (draftQuery.isSuccess) {
      if (draftQuery.data) {
        setSubject(draftQuery.data.subject)
        setContent(draftQuery.data.content)
        setDraftId(draftQuery.data.id)
      }
      setHydrated(true)
    }
  }, [hydrated, generated, type, draftQuery.isSuccess, draftQuery.data])

  function handleRegenerate(nextTone) {
    setTone(nextTone)
    generateMutation.mutate(
      { leadId, type, tone: nextTone },
      {
        onSuccess: (data) => {
          const normalized = fromGenerated(type, data)
          setSubject(normalized.subject)
          setContent(normalized.content)
          setDirty(true)
        },
        onError: (err) => show(err.message),
      }
    )
  }

  function handleSave() {
    saveMutation.mutate(
      { leadId, type, draftId, subject, content },
      {
        onSuccess: (draft) => {
          setDraftId(draft.id)
          setDirty(false)
          show('**Draft saved**')
        },
        onError: (err) => show(err.message),
      }
    )
  }

  function handleContentChange(next) {
    setContent(next)
    setDirty(true)
  }

  function handleSubjectChange(next) {
    setSubject(next)
    setDirty(true)
  }

  const isLoading = !hydrated && (draftQuery.isLoading || !leadQuery.isSuccess)

  return (
    <section>
      <div className="mb-6">
        <button
          onClick={() => setView('askai', params.breadcrumb, { leadId })}
          className="mb-3.5 flex items-center gap-1.5 text-[13px] text-txt-dim transition-colors duration-150 hover:text-signal"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Ask AI
        </button>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-white">
          {TYPE_LABELS[type] ?? 'Outreach'}
        </h1>
        <div className="mt-1.5 flex items-center gap-2 text-[13px]">
          <span className="text-txt-mute">For:</span>
          <span className="font-semibold text-txt">{leadQuery.data?.name ?? '—'}</span>
          {leadQuery.data?.pipeline_stage && (
            <Chip tone="blue" className="font-mono uppercase">
              {leadQuery.data.pipeline_stage.replace('_', ' ')}
            </Chip>
          )}
        </div>
      </div>

      {isLoading ? (
        <div className="grid h-[400px] place-items-center text-[13px] text-txt-mute">Loading…</div>
      ) : (
        <>
          <ToneTabs
            tones={OUTREACH_TONES}
            activeTone={tone}
            onSelect={handleRegenerate}
            pending={generateMutation.isPending}
          />
          <OutreachEditorForm
            type={type}
            subject={subject}
            content={content}
            onSubjectChange={handleSubjectChange}
            onContentChange={handleContentChange}
            dirty={dirty}
            generating={generateMutation.isPending}
          />
        </>
      )}

      <OutreachToolbar
        type={type}
        draftId={draftId}
        onRegenerate={() => handleRegenerate(tone)}
        onSave={handleSave}
        content={content}
        subject={subject}
        regenerating={generateMutation.isPending}
        saving={saveMutation.isPending}
      />
    </section>
  )
}
