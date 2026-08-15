import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useAuditLead } from './useAuditLead'
import { runAudit } from '../services/leadsService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/leadsService', () => ({
  runAudit: vi.fn(),
}))

const AUDIT_RESPONSE = {
  lead_id: 'lead-1',
  ui_score: 6,
  conversion_score: 7,
  content_score: 8,
  trust_score: 8,
  issues: ['Low PageSpeed performance score'],
  summary: 'Overall evaluation text.',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useAuditLead', () => {
  it('calls runAudit with the lead id and returns the audit report on success', async () => {
    runAudit.mockResolvedValue({ ok: true, data: AUDIT_RESPONSE })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAuditLead(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('lead-1')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(runAudit).toHaveBeenCalledWith('lead-1')
    expect(result.current.data).toEqual(AUDIT_RESPONSE)
  })

  it('merges the audit into any cached leads list containing this lead', async () => {
    runAudit.mockResolvedValue({ ok: true, data: AUDIT_RESPONSE })
    const { Wrapper, queryClient } = createQueryWrapper()
    queryClient.setQueryData(['leads', { page: 1 }], {
      total: 1,
      items: [{ id: 'lead-1', name: 'Acme', has_website: true, ai_audited_at: null }],
    })
    const { result } = renderHook(() => useAuditLead(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('lead-1')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const cached = queryClient.getQueryData(['leads', { page: 1 }])
    expect(cached.items[0].ai_ui_score).toBe(6)
    expect(cached.items[0].ai_audited_at).not.toBeNull()
  })

  it('updates the singular lead query cache so a screen reading useLead(id) sees the fresh audit', async () => {
    runAudit.mockResolvedValue({ ok: true, data: AUDIT_RESPONSE })
    const { Wrapper, queryClient } = createQueryWrapper()
    queryClient.setQueryData(['lead', 'lead-1'], { id: 'lead-1', name: 'Acme', has_website: true, ai_audited_at: null })
    const { result } = renderHook(() => useAuditLead(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('lead-1')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    const cachedLead = queryClient.getQueryData(['lead', 'lead-1'])
    expect(cachedLead.ai_ui_score).toBe(6)
    expect(cachedLead.ai_summary).toBe('Overall evaluation text.')
    expect(cachedLead.ai_audited_at).not.toBeNull()
  })

  it('surfaces a 404 not-found message', async () => {
    runAudit.mockResolvedValue({ ok: false, data: { detail: 'Lead not found' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAuditLead(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('missing-lead')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Lead not found')
  })

  it('surfaces a 422 no-website message', async () => {
    runAudit.mockResolvedValue({ ok: false, data: { detail: 'Lead has no website' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAuditLead(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('lead-2')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Lead has no website')
  })

  it('surfaces a retryable 503 message', async () => {
    runAudit.mockResolvedValue({ ok: false, data: { detail: 'AI service unavailable' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useAuditLead(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('lead-3')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('AI service unavailable')
  })
})
