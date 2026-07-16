import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { nextRunPollInterval, useDiscoveryRun } from './useDiscoveryRun'
import { getDiscoveryRun } from '../services/discoveryService'
import { createQueryWrapper } from '../test/queryWrapper'
import { useActiveRunStore } from '../store/useActiveRunStore'

vi.mock('../services/discoveryService', () => ({
  getDiscoveryRun: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  useActiveRunStore.setState({ activeRunId: null })
})

describe('nextRunPollInterval', () => {
  it('keeps polling while pending or running', () => {
    expect(nextRunPollInterval('pending')).toBe(4000)
    expect(nextRunPollInterval('running')).toBe(4000)
  })

  it('stops polling once the run is terminal', () => {
    expect(nextRunPollInterval('completed')).toBe(false)
    expect(nextRunPollInterval('failed')).toBe(false)
    expect(nextRunPollInterval('blocked')).toBe(false)
    expect(nextRunPollInterval('stopped')).toBe(false)
    expect(nextRunPollInterval('skipped_cooldown')).toBe(false)
  })

  it('stops polling when there is no status yet', () => {
    expect(nextRunPollInterval(undefined)).toBe(false)
  })
})

describe('useDiscoveryRun', () => {
  it('returns run data on success', async () => {
    getDiscoveryRun.mockResolvedValue({ ok: true, data: { id: 'run-1', status: 'running', jobs: [], warnings: [] } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDiscoveryRun('run-1'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.data).toBeTruthy())
    expect(result.current.data.status).toBe('running')
  })

  it('surfaces the parsed error message on failure', async () => {
    getDiscoveryRun.mockResolvedValue({ ok: false, data: { error: { message: 'Run not found' } } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDiscoveryRun('missing-run'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Run not found')
  })

  it('does not fetch when runId is falsy', () => {
    const { Wrapper } = createQueryWrapper()
    renderHook(() => useDiscoveryRun(undefined), { wrapper: Wrapper })
    expect(getDiscoveryRun).not.toHaveBeenCalled()
  })

  it('clears the active run pointer once this run reaches a terminal status', async () => {
    useActiveRunStore.getState().setActiveRunId('run-1')
    getDiscoveryRun.mockResolvedValue({ ok: true, data: { id: 'run-1', status: 'completed', jobs: [], warnings: [] } })
    const { Wrapper } = createQueryWrapper()

    renderHook(() => useDiscoveryRun('run-1'), { wrapper: Wrapper })

    await waitFor(() => expect(useActiveRunStore.getState().activeRunId).toBe(null))
  })

  it('does not clear the active run pointer when viewing a different, unrelated run', async () => {
    useActiveRunStore.getState().setActiveRunId('run-active')
    getDiscoveryRun.mockResolvedValue({ ok: true, data: { id: 'run-old', status: 'completed', jobs: [], warnings: [] } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDiscoveryRun('run-old'), { wrapper: Wrapper })
    await waitFor(() => expect(result.current.data).toBeTruthy())

    expect(useActiveRunStore.getState().activeRunId).toBe('run-active')
  })
})
