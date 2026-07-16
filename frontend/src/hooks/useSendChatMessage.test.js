import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useSendChatMessage } from './useSendChatMessage'
import { sendChatMessage } from '../services/leadsService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/leadsService', () => ({
  sendChatMessage: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useSendChatMessage', () => {
  it('optimistically appends the user turn, then appends the assistant reply on success', async () => {
    sendChatMessage.mockResolvedValue({
      ok: true,
      data: { lead_id: 'lead-1', reply: 'Lead with the booking system.', created_at: '2026-07-16T00:00:01Z' },
    })
    const { Wrapper, queryClient } = createQueryWrapper()
    queryClient.setQueryData(['chat-history', 'lead-1'], [])
    const { result } = renderHook(() => useSendChatMessage('lead-1'), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('What should I pitch first?')
    })

    await waitFor(() => {
      const cached = queryClient.getQueryData(['chat-history', 'lead-1'])
      expect(cached).toHaveLength(1)
      expect(cached[0]).toMatchObject({ role: 'user', content: 'What should I pitch first?' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const cached = queryClient.getQueryData(['chat-history', 'lead-1'])
    expect(cached).toHaveLength(2)
    expect(cached[1]).toMatchObject({ role: 'assistant', content: 'Lead with the booking system.' })
  })

  it('surfaces a 503 AI-unavailable message', async () => {
    sendChatMessage.mockResolvedValue({ ok: false, data: { detail: 'AI service unavailable' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useSendChatMessage('lead-1'), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('Hello')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('AI service unavailable')
  })
})
