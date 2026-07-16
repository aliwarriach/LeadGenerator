import { describe, it, expect, beforeEach } from 'vitest'
import { useActiveRunStore } from './useActiveRunStore'

beforeEach(() => {
  useActiveRunStore.setState({ activeRunId: null })
  localStorage.clear()
})

describe('useActiveRunStore', () => {
  it('starts with no active run', () => {
    expect(useActiveRunStore.getState().activeRunId).toBe(null)
  })

  it('setActiveRunId stores the run id', () => {
    useActiveRunStore.getState().setActiveRunId('run-1')
    expect(useActiveRunStore.getState().activeRunId).toBe('run-1')
  })

  it('clearActiveRunId resets to null', () => {
    useActiveRunStore.getState().setActiveRunId('run-1')
    useActiveRunStore.getState().clearActiveRunId()
    expect(useActiveRunStore.getState().activeRunId).toBe(null)
  })

  it('persists to localStorage so a refresh does not lose it', () => {
    useActiveRunStore.getState().setActiveRunId('run-42')
    const stored = JSON.parse(localStorage.getItem('lead-gen-active-run'))
    expect(stored.state.activeRunId).toBe('run-42')
  })
})
