import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useGenerateOutreach } from './useGenerateOutreach'
import { generateEmail, generateWhatsapp, generateProposal } from '../services/outreachService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/outreachService', () => ({
  generateEmail: vi.fn(),
  generateWhatsapp: vi.fn(),
  generateProposal: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useGenerateOutreach', () => {
  it('calls the email generator for type=email and returns the response data', async () => {
    generateEmail.mockResolvedValue({ ok: true, data: { subject: 'Hi', email_body: 'Body' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useGenerateOutreach(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', type: 'email', tone: 'direct' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(generateEmail).toHaveBeenCalledWith('lead-1', 'direct')
    expect(result.current.data).toEqual({ subject: 'Hi', email_body: 'Body' })
  })

  it('calls the whatsapp generator for type=whatsapp', async () => {
    generateWhatsapp.mockResolvedValue({ ok: true, data: { message: 'Hey there' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useGenerateOutreach(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', type: 'whatsapp', tone: 'default' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(generateWhatsapp).toHaveBeenCalledWith('lead-1', 'default')
  })

  it('calls the proposal generator for type=proposal', async () => {
    generateProposal.mockResolvedValue({ ok: true, data: { title: 'Proposal', sections: [] } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useGenerateOutreach(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', type: 'proposal', tone: 'value_first' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(generateProposal).toHaveBeenCalledWith('lead-1', 'value_first')
  })

  it('surfaces a 503 AI-unavailable message', async () => {
    generateEmail.mockResolvedValue({ ok: false, data: { detail: 'AI service unavailable' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useGenerateOutreach(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', type: 'email', tone: 'default' })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('AI service unavailable')
  })
})
