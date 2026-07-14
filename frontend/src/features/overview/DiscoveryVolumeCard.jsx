import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import BarChart from '../../components/charts/BarChart'
import { DISCOVERY_VOLUME, DISCOVERY_VOLUME_TOTAL } from '../../constants/overview'

export default function DiscoveryVolumeCard() {
  return (
    <Card>
      <div className="flex items-center justify-between px-5 pt-4">
        <h3 className="text-sm font-semibold text-white">Discovery volume — last 7 days</h3>
        <Chip tone="muted" className="font-mono">
          {DISCOVERY_VOLUME_TOTAL}
        </Chip>
      </div>
      <BarChart data={DISCOVERY_VOLUME} />
      <div className="flex gap-4 px-5 pb-4 text-[11.5px] text-txt-dim">
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2 w-2 rounded-sm bg-signal" />
          Has website
        </span>
        <span className="flex items-center gap-1.5">
          <i className="inline-block h-2 w-2 rounded-sm bg-[#1f5e45]" />
          No website
        </span>
      </div>
    </Card>
  )
}
