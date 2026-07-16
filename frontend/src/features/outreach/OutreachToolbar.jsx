import { RefreshCw, Save, FileDown, Copy } from 'lucide-react'
import { useGenerateProposalPdf } from '../../hooks/useGenerateProposalPdf'
import { useToastStore } from '../../store/useToastStore'

const BTN =
  'flex items-center gap-1.5 rounded-full border border-line-hi px-3.5 py-2 text-[11.5px] font-semibold uppercase tracking-wide text-txt transition-colors duration-150 hover:bg-ink-soft disabled:cursor-not-allowed disabled:opacity-50'

export default function OutreachToolbar({ type, draftId, onRegenerate, onSave, content, subject, regenerating, saving }) {
  const show = useToastStore((s) => s.show)
  const pdfMutation = useGenerateProposalPdf()

  function handleCopy() {
    const text = type === 'email' && subject ? `${subject}\n\n${content}` : content
    navigator.clipboard.writeText(text)
    show('**Copied** to clipboard')
  }

  function handleGeneratePdf() {
    if (!draftId) {
      show('Save the draft before generating a PDF')
      return
    }
    pdfMutation.mutate(draftId, { onError: (err) => show(err.message) })
  }

  return (
    <div className="pointer-events-none fixed bottom-6 left-[228px] right-0 z-40 flex justify-center">
      <div className="pointer-events-auto flex items-center gap-2 rounded-full border border-line-hi bg-ink-card/95 px-3.5 py-2 shadow-2xl backdrop-blur-md">
        <button onClick={onRegenerate} disabled={regenerating} className={BTN}>
          <RefreshCw className={`h-3.5 w-3.5 ${regenerating ? 'animate-spin' : ''}`} /> Regenerate AI
        </button>
        <button onClick={onSave} disabled={saving} className={BTN}>
          <Save className="h-3.5 w-3.5" /> {saving ? 'Saving…' : 'Save Draft'}
        </button>
        <div className="mx-1 h-6 w-px bg-line" />
        {type === 'proposal' && (
          <button
            onClick={handleGeneratePdf}
            disabled={pdfMutation.isPending}
            className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-[11.5px] font-bold uppercase tracking-wide text-[#08110d] shadow-[0_0_15px_rgba(62,207,142,0.3)] transition-colors duration-150 hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <FileDown className="h-3.5 w-3.5" /> {pdfMutation.isPending ? 'Generating…' : 'Generate PDF'}
          </button>
        )}
        <div className="mx-1 h-6 w-px bg-line" />
        <button title="Copy to clipboard" onClick={handleCopy} className="rounded-full p-2 text-txt-dim transition-colors duration-150 hover:bg-ink-soft hover:text-txt">
          <Copy className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
