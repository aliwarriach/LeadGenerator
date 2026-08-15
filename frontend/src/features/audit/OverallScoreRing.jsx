import RadialProgress from '../../components/charts/RadialProgress'

// A never-scored lead has score == null (website_score is only ever set once
// PageSpeed has actually run) — rendering that as a literal "0/100" ring is
// indistinguishable from a real, bad score of zero. Show an honest dashed
// placeholder instead, with copy that tells the two null cases apart (no
// website to score at all, vs. has one but PageSpeed hasn't scored it yet).
export default function OverallScoreRing({ score, hasWebsite = true }) {
  if (score == null) {
    return (
      <div className="flex flex-col items-center px-6 py-6 text-center">
        <div
          className="grid place-items-center rounded-full border-[11px] border-dashed border-line"
          style={{ width: 150, height: 150 }}
        >
          <span className="text-[13px] font-medium text-txt-mute">{hasWebsite ? 'Not scored' : 'No website'}</span>
        </div>
        <div className="mt-3 text-[11px] uppercase tracking-widest text-txt-mute">Overall score</div>
        <div className="mt-2.5 text-[10.5px] leading-relaxed text-txt-mute">
          {hasWebsite
            ? 'Score appears once PageSpeed analysis completes.'
            : 'This business has no website to score.'}
        </div>
      </div>
    )
  }

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
