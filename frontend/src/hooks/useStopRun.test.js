import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useStopRun } from './useStopRun'
import { stopDiscoveryRun } from '../services/discoveryService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/discoveryService', () => ({
  stopDiscoveryRun: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useStopRun', () => {
  it('resolves with the updated run on success', async () => {
    stopDiscoveryRun.mockResolvedValue({ ok: true, data: { id: 'run-1', status: 'running' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useStopRun('run-1'), { wrapper: Wrapper })

    await act(async () => {
      await result.current.mutateAsync()
    })

    expect(stopDiscoveryRun).toHaveBeenCalledWith('run-1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })

  it('surfaces the parsed error message on failure', async () => {
    stopDiscoveryRun.mockResolvedValue({ ok: false, data: { error: { message: 'Run already finished' } } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useStopRun('run-1'), { wrapper: Wrapper })

    act(() => {
      result.current.mutate()
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Run already finished')
  })
})
