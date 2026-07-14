import Card from '../../components/ui/Card'
import DonutChart from '../../components/charts/DonutChart'
import { LEAD_STAGE_MIX } from '../../constants/overview'

export default function LeadStageMixCard() {
  const total = LEAD_STAGE_MIX.reduce((sum, d) => sum + d.count, 0)

  return (
    <Card>
      <div className="px-5 pt-4">
        <h3 className="text-sm font-semibold text-white">Lead stage mix</h3>
      </div>
      <div className="flex items-center gap-[22px] px-5 pb-5 pt-[18px]">
        <DonutChart data={LEAD_STAGE_MIX} centerValue={total} centerLabel="leads" />
        <div className="flex flex-1 flex-col gap-2.5">
          {LEAD_STAGE_MIX.map((d) => (
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
    </Card>
  )
}
