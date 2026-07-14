import PageHeader from '../../components/ui/PageHeader'
import Button from '../../components/ui/Button'
import StatsGrid from './StatsGrid'
import DiscoveryVolumeCard from './DiscoveryVolumeCard'
import LeadStageMixCard from './LeadStageMixCard'
import ActivityFeed from './ActivityFeed'
import { useViewStore } from '../../store/useViewStore'

export default function OverviewView() {
  const setView = useViewStore((s) => s.setView)

  return (
    <section>
      <PageHeader
        breadcrumb="Workspace"
        title="Overview"
        subtitle="Your discovery-to-deal funnel at a glance."
        actions={<Button onClick={() => setView('discovery')}>＋ New discovery</Button>}
      />
      <StatsGrid />
      <div className="mb-3.5 grid grid-cols-1 gap-3.5 xl:grid-cols-[1.6fr_1fr]">
        <DiscoveryVolumeCard />
        <LeadStageMixCard />
      </div>
      <ActivityFeed />
    </section>
  )
}
