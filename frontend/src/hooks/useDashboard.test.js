import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useDashboardStats, useDiscoveryVolume, useLeadStageMix, useRecentActivity } from './useDashboard'
import { getDashboardStats, getDiscoveryVolume, getLeadStageMix, getRecentActivity } from '../services/dashboardService'
import { createQueryWrapper } from '../test/queryWrapper'

vi.mock('../services/dashboardService', () => ({
  getDashboardStats: vi.fn(),
  getDiscoveryVolume: vi.fn(),
  getLeadStageMix: vi.fn(),
  getRecentActivity: vi.fn(),
}))

describe('useDashboardStats', () => {
  it('returns stats on success', async () => {
    getDashboardStats.mockResolvedValue({ ok: true, data: { discovered_total: 100 } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDashboardStats(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.data).toBeTruthy())
    expect(result.current.data.discovered_total).toBe(100)
  })

  it('surfaces the parsed error message on failure', async () => {
    getDashboardStats.mockResolvedValue({ ok: false, data: { error: { message: 'Database connection failed' } } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useDashboardStats(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error.message).toBe('Database connection failed')
  })
})

describe('useDiscoveryVolume', () => {
  it('fetches with the given day range', async () => {
    getDiscoveryVolume.mockResolvedValue({ ok: true, data: { days: [], total: 0 } })
    const { Wrapper } = createQueryWrapper()

    renderHook(() => useDiscoveryVolume(14), { wrapper: Wrapper })

    await waitFor(() => expect(getDiscoveryVolume).toHaveBeenCalledWith(14))
  })
})

describe('useLeadStageMix', () => {
  it('returns stage mix on success', async () => {
    getLeadStageMix.mockResolvedValue({ ok: true, data: { items: [], total: 0 } })
    const { Wrapper } = createQueryWrapper()

    const { result } = renderHook(() => useLeadStageMix(), { wrapper: Wrapper })

    await waitFor(() => expect(result.current.data).toBeTruthy())
  })
})

describe('useRecentActivity', () => {
  it('fetches with the given limit', async () => {
    getRecentActivity.mockResolvedValue({ ok: true, data: { items: [] } })
    const { Wrapper } = createQueryWrapper()

    renderHook(() => useRecentActivity(5), { wrapper: Wrapper })

    await waitFor(() => expect(getRecentActivity).toHaveBeenCalledWith(5))
  })
})
