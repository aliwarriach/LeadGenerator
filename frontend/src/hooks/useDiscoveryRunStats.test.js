import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useDiscoveryRunStats } from './useDiscoveryRunStats'
import { getDiscoveryRunStats } from '../services/discoveryService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/discoveryService', () => ({
  getDiscoveryRunStats: vi.fn(),
}))

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useDiscoveryRunStats', () => {
  it('returns stats data on success', async () => {
    getDiscoveryRunStats.mockResolvedValue({
      ok: true,
      data: { completed_run_count: 5, avg_duration_seconds: 245.5, avg_leads_saved: 12.4 },
    })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDiscoveryRunStats(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.data).toBeTruthy())
    expect(result.current.data.completed_run_count).toBe(5)
  })

  it('surfaces the parsed error message on failure', async () => {
    getDiscoveryRunStats.mockResolvedValue({ ok: false, data: { error: { message: 'Failed to load run stats' } } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDiscoveryRunStats(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Failed to load run stats')
  })
})
