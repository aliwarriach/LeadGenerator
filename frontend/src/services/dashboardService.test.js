import { describe, it, expect, vi } from 'vitest'
import { api } from './api'
import { getDashboardStats, getDiscoveryVolume, getLeadStageMix, getRecentActivity } from './dashboardService'

vi.mock('./api', () => ({
  api: { get: vi.fn() },
}))

describe('dashboardService', () => {
  it('getDashboardStats fetches the stats resource', () => {
    getDashboardStats()
    expect(api.get).toHaveBeenCalledWith('/dashboard/stats')
  })

  it('getDiscoveryVolume defaults to 7 days', () => {
    getDiscoveryVolume()
    expect(api.get).toHaveBeenCalledWith('/dashboard/discovery-volume', { days: 7 })
  })

  it('getDiscoveryVolume passes a custom day range', () => {
    getDiscoveryVolume(14)
    expect(api.get).toHaveBeenCalledWith('/dashboard/discovery-volume', { days: 14 })
  })

  it('getLeadStageMix fetches the stage-mix resource', () => {
    getLeadStageMix()
    expect(api.get).toHaveBeenCalledWith('/dashboard/lead-stage-mix')
  })

  it('getRecentActivity defaults to a limit of 10', () => {
    getRecentActivity()
    expect(api.get).toHaveBeenCalledWith('/dashboard/activity', { limit: 10 })
  })

  it('getRecentActivity passes a custom limit', () => {
    getRecentActivity(5)
    expect(api.get).toHaveBeenCalledWith('/dashboard/activity', { limit: 5 })
  })
})
