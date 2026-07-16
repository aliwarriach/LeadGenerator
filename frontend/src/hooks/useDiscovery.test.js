import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useDiscovery } from './useDiscovery'
import { startDiscovery } from '../services/discoveryService'

vi.mock('../services/discoveryService', () => ({
  startDiscovery: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useDiscovery', () => {
  it('returns the run payload on success and toggles running', async () => {
    startDiscovery.mockResolvedValue({
      ok: true,
      data: { run_id: 'run-1', jobs: [{ job_id: 'a' }, { job_id: 'b' }] },
    })

    const { result } = renderHook(() => useDiscovery())
    expect(result.current.running).toBe(false)

    let returned
    await act(async () => {
      returned = await result.current.runDiscovery({ country: 'Pakistan', city: 'Lahore', custom_niche: 'Dentists' })
    })

    expect(returned).toEqual({ run_id: 'run-1', jobs: [{ job_id: 'a' }, { job_id: 'b' }] })
    expect(result.current.running).toBe(false)
    expect(result.current.error).toBe(null)
  })

  it('sets error and rethrows on a non-ok response', async () => {
    startDiscovery.mockResolvedValue({ ok: false, data: { error: { message: 'Queue unavailable' } } })

    const { result } = renderHook(() => useDiscovery())

    await act(async () => {
      await expect(
        result.current.runDiscovery({ country: 'Pakistan', city: 'Lahore', custom_niche: 'Dentists' })
      ).rejects.toThrow('Queue unavailable')
    })

    await waitFor(() => expect(result.current.error).toBe('Queue unavailable'))
    expect(result.current.running).toBe(false)
  })
})
