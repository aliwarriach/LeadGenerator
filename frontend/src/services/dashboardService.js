import { api } from './api'

export function getDashboardStats() {
  return api.get('/dashboard/stats')
}

export function getDiscoveryVolume(days = 7) {
  return api.get('/dashboard/discovery-volume', { days })
}

export function getLeadStageMix() {
  return api.get('/dashboard/lead-stage-mix')
}

export function getRecentActivity(limit = 10) {
  return api.get('/dashboard/activity', { limit })
}
