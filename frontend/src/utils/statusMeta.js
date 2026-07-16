// Shared status vocabulary for both runs and jobs, mapped to Chip tones already
// defined in tailwind.config (no ad hoc colors).
const STATUS_META = {
  pending: { label: 'Pending', tone: 'muted' },
  running: { label: 'Running', tone: 'signal' },
  completed: { label: 'Completed', tone: 'signal' },
  blocked: { label: 'Blocked', tone: 'amber' },
  skipped_cooldown: { label: 'Skipped (cooldown)', tone: 'amber' },
  stopped: { label: 'Stopped', tone: 'muted' },
  failed: { label: 'Failed', tone: 'red' },
}

// A job/run is done changing state on its own — pending/running are the only
// non-terminal statuses (matches the run-status derivation priority order).
const TERMINAL_STATUSES = new Set(['completed', 'failed', 'blocked', 'skipped_cooldown', 'stopped'])

export function statusMeta(status) {
  return STATUS_META[status] ?? { label: status ?? 'Unknown', tone: 'muted' }
}

export function isTerminalStatus(status) {
  return TERMINAL_STATUSES.has(status)
}

export const STATUS_OPTIONS = Object.keys(STATUS_META)
