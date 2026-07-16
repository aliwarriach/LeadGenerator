import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'

export default function IssuesRecommendationsGrid({ issues }) {
  return (
    <Card className="px-5 py-[18px]">
      <h3 className="mb-3">
        <Chip tone="red">Key issues</Chip>
      </h3>
      {issues.map((issue) => (
        <div key={issue} className="flex items-start gap-2.5 border-b border-line py-2.5 text-[12.5px] text-txt-dim last:border-none">
          <span>{issue}</span>
        </div>
      ))}
    </Card>
  )
}
