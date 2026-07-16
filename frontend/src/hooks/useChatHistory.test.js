import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useChatHistory } from './useChatHistory'
import { getChatHistory } from '../services/leadsService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/leadsService', () => ({
  getChatHistory: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useChatHistory', () => {
  it('returns the messages array from the history response', async () => {
    const messages = [{ role: 'user', content: 'Hi', created_at: '2026-07-16T00:00:00Z' }]
    getChatHistory.mockResolvedValue({ ok: true, data: { lead_id: 'lead-1', messages } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useChatHistory('lead-1'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(messages)
  })

  it('surfaces an error message on failure', async () => {
    getChatHistory.mockResolvedValue({ ok: false, data: { detail: 'Lead not found' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useChatHistory('missing'), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Lead not found')
  })

  it('does not fetch when leadId is missing', () => {
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useChatHistory(undefined), { wrapper: Wrapper })
    expect(result.current.fetchStatus).toBe('idle')
    expect(getChatHistory).not.toHaveBeenCalled()
  })
})
