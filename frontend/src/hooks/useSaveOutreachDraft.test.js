import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useSaveOutreachDraft } from './useSaveOutreachDraft'
import { saveOutreachDraft, updateOutreachDraft } from '../services/outreachService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/outreachService', () => ({
  saveOutreachDraft: vi.fn(),
  updateOutreachDraft: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useSaveOutreachDraft', () => {
  it('POSTs a new draft when no draftId is known', async () => {
    const draft = { id: 'draft-1', lead_id: 'lead-1', type: 'email', subject: 'Hi', content: 'Body' }
    saveOutreachDraft.mockResolvedValue({ ok: true, data: draft })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useSaveOutreachDraft(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', type: 'email', draftId: null, subject: 'Hi', content: 'Body' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(saveOutreachDraft).toHaveBeenCalledWith('lead-1', 'email', { subject: 'Hi', content: 'Body' })
    expect(updateOutreachDraft).not.toHaveBeenCalled()
  })

  it('PATCHes the existing draft when a draftId is known', async () => {
    const draft = { id: 'draft-1', lead_id: 'lead-1', type: 'email', subject: 'Hi v2', content: 'Body v2' }
    updateOutreachDraft.mockResolvedValue({ ok: true, data: draft })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useSaveOutreachDraft(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', type: 'email', draftId: 'draft-1', subject: 'Hi v2', content: 'Body v2' })
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(updateOutreachDraft).toHaveBeenCalledWith('draft-1', { subject: 'Hi v2', content: 'Body v2' })
    expect(saveOutreachDraft).not.toHaveBeenCalled()
  })

  it('surfaces an error message on failure', async () => {
    saveOutreachDraft.mockResolvedValue({ ok: false, data: { detail: 'Lead not found' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useSaveOutreachDraft(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'missing', type: 'email', draftId: null, subject: null, content: 'x' })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Lead not found')
  })
})
