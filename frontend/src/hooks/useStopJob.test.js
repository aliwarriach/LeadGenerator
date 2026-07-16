import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useStopJob } from './useStopJob'
import { stopDiscoveryJob } from '../services/discoveryService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/discoveryService', () => ({
  stopDiscoveryJob: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useStopJob', () => {
  it('calls stopDiscoveryJob with the job id passed to mutate', async () => {
    stopDiscoveryJob.mockResolvedValue({ ok: true, data: { id: 'job-1', status: 'stopped' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useStopJob('run-1'), { wrapper: Wrapper })

    await act(async () => {
      await result.current.mutateAsync('job-1')
    })

    expect(stopDiscoveryJob).toHaveBeenCalledWith('job-1')
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.variables).toBe('job-1')
  })

  it('surfaces the parsed error message on failure', async () => {
    stopDiscoveryJob.mockResolvedValue({ ok: false, data: { error: { message: 'Job already terminal' } } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useStopJob(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('job-2')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Job already terminal')
  })
})
