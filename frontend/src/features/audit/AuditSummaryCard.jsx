import { Sparkles } from 'lucide-react'
import Card from '../../components/ui/Card'
import Chip from '../../components/ui/Chip'
import { AI_SUMMARY } from '../../constants/audit'

export default function AuditSummaryCard() {
  return (
    <Card className="mb-3.5 border-l-[3px] border-l-violet px-5 py-[18px]">
      <h3 className="mb-2 flex items-center gap-2 text-[13px] font-semibold text-violet">
        <Sparkles className="h-3.5 w-3.5" strokeWidth={2} /> AI summary
      </h3>
      <p className="text-[13px] leading-relaxed text-txt-dim">{AI_SUMMARY.text}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {AI_SUMMARY.services.map((s) => (
          <Chip key={s} tone="violet">
            {s}
          </Chip>
        ))}
      </div>
    </Card>
  )
}
