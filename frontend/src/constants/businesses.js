export const BUSINESS_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'has', label: 'Has website' },
  { id: 'no', label: 'No website' },
  { id: 'rating45', label: 'Rating ≥ 4.5' },
  { id: 'scoreLow', label: 'Score < 60' },
]

export function scoreTone(score) {
  if (score >= 75) return 'signal'
  if (score >= 60) return 'amber'
  return 'red'
}
