import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useAllLeads } from './useAllLeads'
import { listLeads } from '../services/leadsService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/leadsService', () => ({
  listLeads: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useAllLeads', () => {
  it('returns items from a single page when total_pages is 1', async () => {
    listLeads.mockResolvedValue({
      ok: true,
      data: { items: [{ id: '1' }, { id: '2' }], total: 2, page: 1, page_size: 100, total_pages: 1 },
    })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAllLeads(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listLeads).toHaveBeenCalledTimes(1)
    expect(result.current.data.items).toHaveLength(2)
    expect(result.current.data.total).toBe(2)
  })

  it('merges subsequent pages when total_pages > 1', async () => {
    listLeads
      .mockResolvedValueOnce({
        ok: true,
        data: { items: [{ id: '1' }], total: 2, page: 1, page_size: 1, total_pages: 2 },
      })
      .mockResolvedValueOnce({
        ok: true,
        data: { items: [{ id: '2' }], total: 2, page: 2, page_size: 1, total_pages: 2 },
      })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAllLeads(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(listLeads).toHaveBeenCalledTimes(2)
    expect(result.current.data.items.map((i) => i.id)).toEqual(['1', '2'])
  })

  it('surfaces an error message on failure', async () => {
    listLeads.mockResolvedValue({ ok: false, data: { detail: 'Database connection failed' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAllLeads(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Database connection failed')
  })
})
