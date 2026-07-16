import { useMemo } from 'react'
import Card from '../../components/ui/Card'
import Button from '../../components/ui/Button'
import RadarScan from './RadarScan'
import { RUN_ESTIMATE } from '../../constants/discovery'
import { useToastStore } from '../../store/useToastStore'
import { useViewStore } from '../../store/useViewStore'
import { useActiveRunStore } from '../../store/useActiveRunStore'
import { useDiscovery } from '../../hooks/useDiscovery'
import { buildDiscoveryPayload } from './buildDiscoveryPayload'

export default function RunEstimateCard({ countryId, cityIds, customCity, industryIds, niche, filterIds }) {
  const show = useToastStore((s) => s.show)
  const setView = useViewStore((s) => s.setView)
  const setActiveRunId = useActiveRunStore((s) => s.setActiveRunId)
  const { runDiscovery, running } = useDiscovery()

  const { payload, errors } = useMemo(
    () => buildDiscoveryPayload({ countryId, cityIds, customCity, industryIds, niche, filterIds }),
    [countryId, cityIds, customCity, industryIds, niche, filterIds]
  )

  async function handleRun() {
    if (!payload) {
      show(`**Can't start discovery** — ${errors[0]}`)
      return
    }

    try {
      const result = await runDiscovery(payload)
      const jobCount = result.jobs.length
      setActiveRunId(result.run_id)
      show(`**Discovery started** — tracking ${jobCount} job${jobCount === 1 ? '' : 's'}`)
      setView('run-monitoring', 'Discovery', { runId: result.run_id })
    } catch (err) {
      show(`**Discovery failed** — ${err.message}`)
    }
  }

  return (
    <Card className="px-[22px] py-5">
      <h3 className="mb-1.5 text-sm font-semibold text-white">Run estimate</h3>
      <RadarScan />
      <dl className="divide-y divide-dashed divide-line">
        <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
          <dt title="Text Search caps at 60 results — we split by neighborhood">Fan-out sub-queries ⓘ</dt>
          <dd className="font-mono text-white">{RUN_ESTIMATE.subQueries}</dd>
        </div>
        <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
          <dt>Expected businesses</dt>
          <dd className="font-mono text-white">{RUN_ESTIMATE.expectedRange}</dd>
        </div>
        <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
          <dt>Served from PlaceCache</dt>
          <dd className="font-mono text-signal">{RUN_ESTIMATE.cachedPct}</dd>
        </div>
        <div className="flex justify-between py-2.5 text-[13px] text-txt-dim">
          <dt>Places API cost</dt>
          <dd className="font-mono text-white">{RUN_ESTIMATE.costRange}</dd>
        </div>
      </dl>
      <p className="my-4 rounded-lg border border-line bg-ink-soft px-3 py-2.5 text-[11.5px] leading-relaxed text-txt-mute">
        {RUN_ESTIMATE.note}
      </p>
      <Button
        className={`w-full justify-center ${running ? 'cursor-not-allowed opacity-70' : ''}`}
        disabled={running}
        onClick={handleRun}
      >
        {running ? 'Scanning neighborhoods…' : 'Run discovery'}
      </Button>
    </Card>
  )
}
