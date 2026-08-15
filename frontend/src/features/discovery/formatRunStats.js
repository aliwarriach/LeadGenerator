import { intervalToDuration, formatDuration } from 'date-fns'

export function formatAvgDuration(seconds) {
  if (seconds == null) return null
  const totalSeconds = Math.max(0, Math.round(seconds))
  if (totalSeconds < 60) return `${totalSeconds}s`
  const duration = intervalToDuration({ start: 0, end: totalSeconds * 1000 })
  return formatDuration(duration, { format: ['hours', 'minutes'] }) || `${totalSeconds}s`
}

export function formatAvgLeadsSaved(count) {
  if (count == null) return null
  return `~${Math.round(count)}`
}

export function formatCompletedRunCount(count) {
  if (!count) return 'No completed runs yet'
  return `${count} completed run${count === 1 ? '' : 's'}`
}

export function formatSuccessRate(rate) {
  if (rate == null) return null
  return `${Math.round(rate * 100)}%`
}

export function formatTotalLeadsSaved(count) {
  if (count == null) return null
  return `${count.toLocaleString()} lead${count === 1 ? '' : 's'}`
}
