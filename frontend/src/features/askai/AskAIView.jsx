import { useEffect, useState } from 'react'
import { ArrowLeftRight } from 'lucide-react'
import PageHeader from '../../components/ui/PageHeader'
import Button from '../../components/ui/Button'
import ChatPanel from './ChatPanel'
import OutreachPanel from './OutreachPanel'
import BusinessPickerModal from '../../components/business/BusinessPickerModal'
import { useViewStore } from '../../store/useViewStore'
import { useSelectedLeadStore } from '../../store/useSelectedLeadStore'

export default function AskAIView() {
  const breadcrumb = useViewStore((s) => s.breadcrumb)
  const setView = useViewStore((s) => s.setView)
  const paramLeadId = useViewStore((s) => s.params.leadId)
  const selectedLeadId = useSelectedLeadStore((s) => s.selectedLeadId)
  const setSelectedLeadId = useSelectedLeadStore((s) => s.setSelectedLeadId)
  const leadId = paramLeadId ?? selectedLeadId
  const [pickerOpen, setPickerOpen] = useState(false)

  useEffect(() => {
    if (paramLeadId) setSelectedLeadId(paramLeadId)
  }, [paramLeadId, setSelectedLeadId])

  // Same navigation mechanism used app-wide for a lead-scoped tab switch
  // (see Sidebar.handleNavClick) — the URL/store sync in the effect above
  // then keeps useSelectedLeadStore in sync for free, no duplicate logic.
  function handleSelectBusiness(newLeadId) {
    setView('askai', 'Workspace', { leadId: newLeadId })
    setPickerOpen(false)
  }

  return (
    <section>
      <PageHeader
        breadcrumb={breadcrumb}
        title="Ask AI"
        subtitle="Grounded on this business's data + latest audit. History is saved."
        actions={
          <Button variant="ghost" onClick={() => setPickerOpen(true)}>
            <ArrowLeftRight className="h-3.5 w-3.5" /> Switch business
          </Button>
        }
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_300px]">
        <ChatPanel leadId={leadId} onOpenPicker={() => setPickerOpen(true)} />
        <OutreachPanel leadId={leadId} onOpenPicker={() => setPickerOpen(true)} />
      </div>
      <BusinessPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        activeLeadId={leadId}
        onSelect={handleSelectBusiness}
      />
    </section>
  )
}
