import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useGenerateProposalPdf } from './useGenerateProposalPdf'
import { generateProposalPdf } from '../services/outreachService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/outreachService', () => ({
  generateProposalPdf: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
  global.URL.createObjectURL = vi.fn(() => 'blob:mock-url')
  global.URL.revokeObjectURL = vi.fn()
})

describe('useGenerateProposalPdf', () => {
  it('triggers a browser download of the returned blob on success', async () => {
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' })
    generateProposalPdf.mockResolvedValue({ ok: true, data: blob })
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useGenerateProposalPdf(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('draft-1')
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(generateProposalPdf).toHaveBeenCalledWith('draft-1')
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob)
    expect(clickSpy).toHaveBeenCalled()
    clickSpy.mockRestore()
  })

  it('surfaces a 422 error when the draft is not a proposal', async () => {
    generateProposalPdf.mockResolvedValue({ ok: false, data: { detail: 'Draft is not a proposal' } })
    const { Wrapper } = createQueryWrapper()
    const { result } = renderHook(() => useGenerateProposalPdf(), { wrapper: Wrapper })

    act(() => {
      result.current.mutate('draft-2')
    })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Draft is not a proposal')
  })
})
