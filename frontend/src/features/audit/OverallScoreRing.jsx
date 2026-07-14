import RadialProgress from '../../components/charts/RadialProgress'
import { AUDIT_OVERALL } from '../../constants/audit'

export default function OverallScoreRing() {
  return (
    <div className="flex flex-col items-center px-6 py-6 text-center">
      <RadialProgress value={AUDIT_OVERALL.score} max={AUDIT_OVERALL.max} size={150} strokeWidth={11} color="#f0b429">
        <div className="flex flex-col items-center">
          <span className="font-display text-[34px] font-bold text-white">{AUDIT_OVERALL.score}</span>
          <span className="text-[11px] text-txt-mute">/ {AUDIT_OVERALL.max}</span>
        </div>
      </RadialProgress>
      <div className="mt-3 text-[11px] uppercase tracking-widest text-txt-mute">Overall score</div>
      <div className="mt-2.5 text-[10.5px] leading-relaxed text-txt-mute">
        {AUDIT_OVERALL.formulaLines.map((line) => (
          <div key={line}>{line}</div>
        ))}
      </div>
    </div>
  )
}
