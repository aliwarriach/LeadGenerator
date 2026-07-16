import RadialProgress from '../../components/charts/RadialProgress'

export default function OverallScoreRing({ score }) {
  return (
    <div className="flex flex-col items-center px-6 py-6 text-center">
      <RadialProgress value={score} max={100} size={150} strokeWidth={11} color="#f0b429">
        <div className="flex flex-col items-center">
          <span className="font-display text-[34px] font-bold text-white">{score}</span>
          <span className="text-[11px] text-txt-mute">/ 100</span>
        </div>
      </RadialProgress>
      <div className="mt-3 text-[11px] uppercase tracking-widest text-txt-mute">Overall score</div>
      <div className="mt-2.5 text-[10.5px] leading-relaxed text-txt-mute">Source: Google PageSpeed Insights</div>
    </div>
  )
}
