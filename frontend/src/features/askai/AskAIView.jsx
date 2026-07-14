import PageHeader from '../../components/ui/PageHeader'
import ChatPanel from './ChatPanel'
import OutreachPanel from './OutreachPanel'
import { CHAT_SUBJECT } from '../../constants/askai'

export default function AskAIView() {
  return (
    <section>
      <PageHeader
        breadcrumb={CHAT_SUBJECT.breadcrumb}
        title="Ask AI"
        subtitle="Grounded on this business's data + latest audit (v2). History is saved."
      />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_300px]">
        <ChatPanel />
        <OutreachPanel />
      </div>
    </section>
  )
}
