import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useOutreachDraft } from './useOutreachDraft'
import { getOutreachDraft } from '../services/outreachService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/outreachService', () => ({
  getOutreachDraft: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useOutreachDraft', () => {
  it('returns the saved draft on success', async () => {
    const draft = { id: 'draft-1', lead_id: 'lead-1', type: 'email', subject: 'Hi', content: 'Body' }
    getOutreachDraft.mockResolvedValue({ ok: true, status: 200, data: draft })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useOutreachDraft('lead-1', 'email'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(draft)
  })

  it('resolves to null on a 404 (no draft saved yet) instead of erroring', async () => {
    getOutreachDraft.mockResolvedValue({ ok: false, status: 404, data: { detail: 'Not found' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useOutreachDraft('lead-1', 'proposal'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeNull()
    expect(result.current.isError).toBe(false)
  })

  it('surfaces a non-404 error (e.g. 503 db unavailable)', async () => {
    getOutreachDraft.mockResolvedValue({ ok: false, status: 503, data: { detail: 'Database unavailable' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useOutreachDraft('lead-1', 'email'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Database unavailable')
  })

  it('does not fetch when leadId or type is missing', () => {
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useOutreachDraft(null, 'email'), { wrapper: Wrapper })
    expect(result.current.fetchStatus).toBe('idle')
    expect(getOutreachDraft).not.toHaveBeenCalled()
  })
})
