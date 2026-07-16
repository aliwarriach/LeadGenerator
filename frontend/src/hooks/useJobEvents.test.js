import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useJobEvents } from './useJobEvents'
import { getJobEvents } from '../services/discoveryService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/discoveryService', () => ({
  getJobEvents: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useJobEvents', () => {
  it('omits `after` on the first fetch and accumulates items across polls', async () => {
    getJobEvents.mockResolvedValueOnce({
      ok: true,
      data: { items: [{ id: 1, message: 'Starting scraper' }], next_cursor: 1 },
    })
    const { Wrapper, queryClient } = createQueryWrapper()

    const { result } = renderHook(() => useJobEvents('job-1'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.data?.items).toHaveLength(1))
    expect(getJobEvents).toHaveBeenCalledWith('job-1', { after: undefined })

    getJobEvents.mockResolvedValueOnce({
      ok: true,
      data: { items: [{ id: 2, message: 'Found a lead' }], next_cursor: 2 },
    })
    await queryClient.refetchQueries({ queryKey: ['job-events', 'job-1'] })

    await waitFor(() => expect(result.current.data?.items).toHaveLength(2))
    expect(getJobEvents).toHaveBeenLastCalledWith('job-1', { after: 1 })
    expect(result.current.data.items.map((e) => e.id)).toEqual([1, 2])
  })

  it('keeps reusing the last cursor when next_cursor is null', async () => {
    getJobEvents.mockResolvedValueOnce({ ok: true, data: { items: [{ id: 1, message: 'x' }], next_cursor: 5 } })
    const { Wrapper, queryClient } = createQueryWrapper()
    const { result } = renderHook(() => useJobEvents('job-2'), { wrapper: Wrapper })
    await waitFor(() => expect(result.current.data?.items).toHaveLength(1))

    getJobEvents.mockResolvedValueOnce({ ok: true, data: { items: [], next_cursor: null } })
    await queryClient.refetchQueries({ queryKey: ['job-events', 'job-2'] })
    await waitFor(() => expect(getJobEvents).toHaveBeenCalledTimes(2))

    getJobEvents.mockResolvedValueOnce({ ok: true, data: { items: [{ id: 2, message: 'y' }], next_cursor: 6 } })
    await queryClient.refetchQueries({ queryKey: ['job-events', 'job-2'] })

    await waitFor(() => expect(getJobEvents).toHaveBeenLastCalledWith('job-2', { after: 5 }))
  })

  it('does not fetch when disabled', () => {
    const { Wrapper } = createQueryWrapper()
    renderHook(() => useJobEvents('job-3', { enabled: false }), { wrapper: Wrapper })
    expect(getJobEvents).not.toHaveBeenCalled()
  })
})
