import { describe, it, expect } from 'vitest'
import { statusMeta, isTerminalStatus, STATUS_OPTIONS } from './statusMeta'

describe('statusMeta', () => {
  it('maps every documented status to a label and tone', () => {
    for (const status of STATUS_OPTIONS) {
      const meta = statusMeta(status)
      expect(meta.label).toBeTruthy()
      expect(meta.tone).toBeTruthy()
    }
  })

  it('falls back gracefully for an unrecognized status', () => {
    expect(statusMeta('something_new')).toEqual({ label: 'something_new', tone: 'muted' })
  })

  it('falls back for a nullish status', () => {
    expect(statusMeta(undefined)).toEqual({ label: 'Unknown', tone: 'muted' })
  })
})

describe('isTerminalStatus', () => {
  it('treats pending/running as non-terminal', () => {
    expect(isTerminalStatus('pending')).toBe(false)
    expect(isTerminalStatus('running')).toBe(false)
  })

  it('treats completed/failed/blocked/skipped_cooldown/stopped as terminal', () => {
    expect(isTerminalStatus('completed')).toBe(true)
    expect(isTerminalStatus('failed')).toBe(true)
    expect(isTerminalStatus('blocked')).toBe(true)
    expect(isTerminalStatus('skipped_cooldown')).toBe(true)
    expect(isTerminalStatus('stopped')).toBe(true)
  })
})
