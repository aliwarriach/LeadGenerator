import Sidebar from './components/layout/Sidebar'
import Toast from './components/ui/Toast'
import { useViewStore } from './store/useViewStore'
import OverviewView from './features/overview/OverviewView'
import DiscoveryView from './features/discovery/DiscoveryView'
import BusinessesView from './features/businesses/BusinessesView'
import AuditView from './features/audit/AuditView'
import AskAIView from './features/askai/AskAIView'
import OutreachEditorView from './features/outreach/OutreachEditorView'
import PipelineView from './features/pipeline/PipelineView'
import RunMonitoringView from './features/runMonitoring/RunMonitoringView'
import RunHistoryView from './features/runHistory/RunHistoryView'
import JobQueueView from './features/jobQueue/JobQueueView'

const VIEWS = {
  overview: OverviewView,
  discovery: DiscoveryView,
  businesses: BusinessesView,
  audit: AuditView,
  askai: AskAIView,
  'outreach-editor': OutreachEditorView,
  pipeline: PipelineView,
  'run-monitoring': RunMonitoringView,
  'run-history': RunHistoryView,
  'job-queue': JobQueueView,
}

function App() {
  const view = useViewStore((s) => s.view)
  const ActiveView = VIEWS[view]

  return (
    <div className="flex min-h-screen bg-ink">
      <Sidebar />
      <main className="min-w-0 flex-1 px-4 pb-16 pt-7 sm:px-8">
        <ActiveView />
      </main>
      <Toast />
    </div>
  )
}

export default App
