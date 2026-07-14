import { api } from './api'

export function startDiscovery(payload) {
  return api.post('/start-discovery', payload)
}

export function getJobStatus(jobId) {
  return api.get(`/discovery-jobs/${jobId}`)
}
