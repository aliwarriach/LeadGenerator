import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import { KEY_ISSUES, RECOMMENDATIONS } from '../../constants/audit'

const SEVERITY_TONE = { High: 'red', Med: 'amber', Low: 'muted' }

export default function IssuesRecommendationsGrid() {
  return (
    <div className="grid grid-cols-1 gap-3.5 lg:grid-cols-2">
      <Card className="px-5 py-[18px]">
        <h3 className="mb-3">
          <Chip tone="red">Key issues</Chip>
        </h3>
        {KEY_ISSUES.map((issue) => (
          <div
            key={issue.text}
            className="flex items-start gap-2.5 border-b border-line py-2.5 text-[12.5px] text-txt-dim last:border-none"
          >
            <Chip tone={SEVERITY_TONE[issue.severity]} className="mt-0.5 shrink-0">
              {issue.severity}
            </Chip>
            <span>{issue.text}</span>
          </div>
        ))}
      </Card>
      <Card className="px-5 py-[18px]">
        <h3 className="mb-3">
          <Chip tone="signal">Recommendations</Chip>
        </h3>
        {RECOMMENDATIONS.map((text, i) => (
          <div
            key={text}
            className="flex items-start gap-2.5 border-b border-line py-2.5 text-[12.5px] text-txt-dim last:border-none"
          >
            <span className="shrink-0 text-txt-mute">{i + 1}.</span>
            <span>{text}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
