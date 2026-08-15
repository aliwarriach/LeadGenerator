import { Fragment, useState } from 'react'
import { BarChart3, ShieldCheck, Sparkles, Mail, Plus, Check } from 'lucide-react'
import Chip from '../../components/ui/Chip'
import { scoreTone } from '../../constants/businesses'
import { useViewStore } from '../../store/useViewStore'
import { useToastStore } from '../../store/useToastStore'
import { useAuditLead } from '../../hooks/useAuditLead'
import { useGenerateOutreach } from '../../hooks/useGenerateOutreach'
import { useUpdateLeadStage } from '../../hooks/useUpdateLeadStage'
import AuditReportPanel from './AuditReportPanel'

const HEADERS = ['Business', 'Rating', 'Website', 'Score', 'Actions']
const ACTION_BTN =
  'grid h-[29px] w-[29px] shrink-0 place-items-center rounded-lg border border-line-hi text-txt-dim transition-colors duration-150 hover:border-signal hover:text-signal disabled:pointer-events-none disabled:opacity-50'
const SPINNER = 'h-3 w-3 animate-spin rounded-full border-2 border-txt-dim border-t-transparent'

export default function BusinessTable({ businesses }) {
  const setView = useViewStore((s) => s.setView)
  const show = useToastStore((s) => s.show)
  const [expandedId, setExpandedId] = useState(null)
  const auditMutation = useAuditLead()
  const outreachMutation = useGenerateOutreach()
  const stageMutation = useUpdateLeadStage()

  function openLeadView(view, business) {
    setView(view, `Businesses / ${business.name}`, { leadId: business.id })
  }

  if (businesses.length === 0) {
    return <p className="px-5 py-10 text-center text-[13px] text-txt-mute">No businesses match these filters.</p>
  }

  function handleToggleAudit(business) {
    const nextExpanded = expandedId === business.id ? null : business.id
    setExpandedId(nextExpanded)
    if (nextExpanded && !business.audit) {
      auditMutation.mutate(business.id)
    }
  }

  // Generates real content via the same Groq-backed flow as Ask AI's
  // outreach panel, then lands the user on the real editor with it —
  // no fake "drafted" toast with nothing behind it.
  function handleGenerateOutreach(business) {
    const breadcrumb = `Businesses / ${business.name}`
    outreachMutation.mutate(
      { leadId: business.id, type: 'email', tone: 'default' },
      {
        onSuccess: (data) => {
          setView('outreach-editor', breadcrumb, { leadId: business.id, type: 'email', generated: data, breadcrumb })
        },
        onError: (err) => show(err.message),
      }
    )
  }

  // Every lead already starts in the pipeline at "new_lead" (backend
  // default), so "save" can't mean "add" — it means the user has decided to
  // actively pursue it, i.e. advance it to "contacted", same real mutation
  // the Pipeline board's drag-and-drop uses.
  function handleSaveLead(business) {
    if (business.pipelineStage !== 'new_lead') return
    stageMutation.mutate(
      { leadId: business.id, stage: 'contacted' },
      {
        onSuccess: () => show(`**${business.name}** moved to Contacted — logged to activity`),
        onError: (err) => show(err.message),
      }
    )
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
          {businesses.map((b) => {
            const isExpanded = expandedId === b.id
            const isPending = auditMutation.isPending && auditMutation.variables === b.id
            const isError = auditMutation.isError && auditMutation.variables === b.id
            const isOutreachPending = outreachMutation.isPending && outreachMutation.variables?.leadId === b.id
            const isStagePending = stageMutation.isPending && stageMutation.variables?.leadId === b.id
            const isSaved = b.pipelineStage != null && b.pipelineStage !== 'new_lead'
            return (
              <Fragment key={b.id}>
                <tr className="border-b border-line transition-colors duration-100 last:border-none hover:bg-signal/[.03]">
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
                      <a
                        href={b.websiteHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Open ${b.website} in a new tab`}
                        className="font-mono text-[12px] text-blue underline decoration-blue/30 underline-offset-2 transition-colors duration-150 hover:text-signal hover:decoration-signal/40"
                      >
                        {b.website}
                      </a>
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
                      {b.hasWebsite && (
                        <button
                          title={b.audit ? 'Re-run AI audit' : 'Run AI Audit'}
                          onClick={() => handleToggleAudit(b)}
                          aria-expanded={isExpanded}
                          className={ACTION_BTN}
                        >
                          <BarChart3 className="h-3.5 w-3.5" />
                        </button>
                      )}
                      {b.hasWebsite && (
                        <button
                          title="View full audit report"
                          onClick={() => openLeadView('audit', b)}
                          className={ACTION_BTN}
                        >
                          <ShieldCheck className="h-3.5 w-3.5" />
                        </button>
                      )}
                      <button
                        title="Ask AI"
                        onClick={() => openLeadView('askai', b)}
                        className={ACTION_BTN}
                      >
                        <Sparkles className="h-3.5 w-3.5" />
                      </button>
                      <button
                        title="Generate outreach email"
                        onClick={() => handleGenerateOutreach(b)}
                        disabled={isOutreachPending}
                        className={ACTION_BTN}
                      >
                        {isOutreachPending ? <span className={SPINNER} /> : <Mail className="h-3.5 w-3.5" />}
                      </button>
                      {isSaved ? (
                        <span
                          title={`Already ${b.pipelineStage.replace('_', ' ')}`}
                          className={`${ACTION_BTN} cursor-default border-signal/40 text-signal hover:border-signal/40 hover:text-signal`}
                        >
                          <Check className="h-3.5 w-3.5" />
                        </span>
                      ) : (
                        <button
                          title="Move to Contacted"
                          onClick={() => handleSaveLead(b)}
                          disabled={isStagePending}
                          className={ACTION_BTN}
                        >
                          {isStagePending ? <span className={SPINNER} /> : <Plus className="h-3.5 w-3.5" />}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
                {isExpanded && (
                  <tr className="border-b border-line last:border-none">
                    <td colSpan={HEADERS.length} className="px-3.5 py-3">
                      <AuditReportPanel
                        audit={b.audit}
                        pending={isPending}
                        error={isError ? auditMutation.error.message : null}
                        onRetry={() => auditMutation.mutate(b.id)}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
