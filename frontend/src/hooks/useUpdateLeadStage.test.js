import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useUpdateLeadStage } from './useUpdateLeadStage'
import { updateLeadStage } from '../services/leadsService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/leadsService', () => ({
  updateLeadStage: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useUpdateLeadStage', () => {
  it('optimistically moves the lead in the cache, then confirms on success', async () => {
    updateLeadStage.mockResolvedValue({ ok: true, data: { id: 'lead-1', pipeline_stage: 'contacted' } })
    const { Wrapper, queryClient } = createQueryWrapper()
    queryClient.setQueryData(['leads', 'all'], {
      items: [{ id: 'lead-1', pipeline_stage: 'new_lead' }],
      total: 1,
    })
    const { result } = renderHook(() => useUpdateLeadStage(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', stage: 'contacted' })
    })

    await waitFor(() => {
      const cached = queryClient.getQueryData(['leads', 'all'])
      expect(cached.items[0].pipeline_stage).toBe('contacted')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
  })

  it('rolls back the optimistic move on failure', async () => {
    updateLeadStage.mockResolvedValue({ ok: false, data: { detail: 'Lead not found' } })
    const { Wrapper, queryClient } = createQueryWrapper()
    queryClient.setQueryData(['leads', 'all'], {
      items: [{ id: 'lead-1', pipeline_stage: 'new_lead' }],
      total: 1,
    })
    const { result } = renderHook(() => useUpdateLeadStage(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate({ leadId: 'lead-1', stage: 'contacted' })
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Lead not found')
    const cached = queryClient.getQueryData(['leads', 'all'])
    expect(cached.items[0].pipeline_stage).toBe('new_lead')
  })
})
