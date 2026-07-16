import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import DonutChart from '../../components/charts/DonutChart'
import { useLeadStageMix } from '../../hooks/useDashboard'
import { PIPELINE_STAGES } from '../../constants/pipeline'

function mapMixToChart(items) {
  return items.map((item) => {
    const stage = PIPELINE_STAGES.find((s) => s.id === item.stage)
    return { stage: stage?.label ?? item.stage, count: item.count, color: stage?.color ?? '#5c6b7d' }
  })
}

export default function LeadStageMixCard() {
  const { data, isLoading, isError, error, refetch } = useLeadStageMix()

  return (
    <Card>
      <div className="px-5 pt-4">
        <h3 className="text-sm font-semibold text-white">Lead stage mix</h3>
      </div>
      {isLoading ? (
        <div className="flex items-center gap-[22px] px-5 pb-5 pt-[18px]">
          <div className="h-[120px] w-[120px] shrink-0 animate-pulse rounded-full bg-line" />
          <div className="flex flex-1 flex-col gap-2.5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-3 animate-pulse rounded bg-line" />
            ))}
          </div>
        </div>
      ) : isError ? (
        <div className="px-5 py-10 text-center text-[13px]">
          <p className="mb-3 text-red">{error.message}</p>
          <Button variant="ghost" onClick={() => refetch()}>
            Retry
          </Button>
        </div>
      ) : data.total === 0 ? (
        <p className="px-5 py-10 text-center text-[13px] text-txt-mute">No leads yet.</p>
      ) : (
        <div className="flex items-center gap-[22px] px-5 pb-5 pt-[18px]">
          <DonutChart data={mapMixToChart(data.items)} centerValue={data.total} centerLabel="leads" />
          <div className="flex flex-1 flex-col gap-2.5">
            {mapMixToChart(data.items).map((d) => (
              <div key={d.stage} className="flex justify-between text-[12.5px]">
                <span className="flex items-center gap-1.5 text-txt-dim">
                  <i className="inline-block h-2 w-2 rounded-sm" style={{ background: d.color }} />
                  {d.stage}
                </span>
                <b className="font-mono font-medium text-white">{d.count}</b>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}
