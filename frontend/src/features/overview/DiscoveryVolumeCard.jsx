import { format, parseISO } from 'date-fns'
import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import Button from '../../components/ui/Button'
import BarChart from '../../components/charts/BarChart'
import { useDiscoveryVolume } from '../../hooks/useDashboard'

function mapVolumeToChart(days) {
  return days.map((d) => ({
    day: format(parseISO(d.day), 'EEE'),
    hasWebsite: d.has_website,
    noWebsite: d.no_website,
  }))
}

export default function DiscoveryVolumeCard() {
  const { data, isLoading, isError, error, refetch } = useDiscoveryVolume(7)

  return (
    <Card>
      <div className="flex items-center justify-between px-5 pt-4">
        <h3 className="text-sm font-semibold text-white">Discovery volume — last 7 days</h3>
        {!isLoading && !isError && (
          <Chip tone="muted" className="font-mono">
            {data.total.toLocaleString()} total
          </Chip>
        )}
      </div>
      {isLoading ? (
        <div className="h-[150px] animate-pulse px-5 pb-2 pt-[18px]">
          <div className="h-full rounded-lg bg-line" />
        </div>
      ) : isError ? (
        <div className="px-5 py-10 text-center text-[13px]">
          <p className="mb-3 text-red">{error.message}</p>
          <Button variant="ghost" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : (
        <>
          <BarChart data={mapVolumeToChart(data.days)} />
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
        </>
      )}
    </Card>
  )
}
