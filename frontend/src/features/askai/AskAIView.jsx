import PageHeader from '../../components/ui/PageHeader'
import ChatPanel from './ChatPanel'
import OutreachPanel from './OutreachPanel'
import { useViewStore } from '../../store/useViewStore'

export default function AskAIView() {
  const breadcrumb = useViewStore((s) => s.breadcrumb)
  const leadId = useViewStore((s) => s.params.leadId)

  return (
    <section>
      <PageHeader
        breadcrumb={breadcrumb}
        title="Ask AI"
        subtitle="Grounded on this business's data + latest audit. History is saved."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_300px]">
        <ChatPanel leadId={leadId} />
        <OutreachPanel />
      </div>
    </section>
  )
}
