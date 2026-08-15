import { api } from './api'

export function startDiscovery(payload) {
  return api.post('/start-discovery', payload)
}

// Standalone single-job resource — the only place total_leads_scraped_by_source
// is actually populated (all-time count for that source, not scoped to one run).
export function getJob(jobId) {
  return api.get(`/discovery-jobs/${jobId}`)
}

export function getDiscoveryRun(runId) {
  return api.get(`/discovery-runs/${runId}`)
}

export function stopDiscoveryRun(runId) {
  return api.post(`/discovery-runs/${runId}/stop`)
}

export function stopDiscoveryJob(jobId) {
  return api.post(`/discovery-jobs/${jobId}/stop`)
}

// next_cursor is a bookmark, not a "has more" flag — callers must keep
// resending their last known cursor even after an empty `items` page.
export function getJobEvents(jobId, { after, limit = 50 } = {}) {
  const params = { limit }
  if (after != null) params.after = after
  return api.get(`/discovery-jobs/${jobId}/events`, params)
}

export function listDiscoveryRuns(params) {
  return api.get('/discovery-runs', params)
}

export function getDiscoveryRunStats() {
  return api.get('/discovery-runs/stats')
}

export function listDiscoveryJobs(params) {
  return api.get('/discovery-jobs', params)
}
