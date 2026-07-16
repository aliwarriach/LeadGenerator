import { describe, it, expect, vi } from 'vitest'
import { api } from './api'
import {
  startDiscovery,
  getJob,
  getDiscoveryRun,
  stopDiscoveryRun,
  stopDiscoveryJob,
  getJobEvents,
  listDiscoveryRuns,
  listDiscoveryJobs,
} from './discoveryService'

vi.mock('./api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
}))

describe('discoveryService', () => {
  it('startDiscovery posts the payload', () => {
    const payload = { country: 'Pakistan', city: 'Lahore', custom_niche: 'Dentists' }
    startDiscovery(payload)
    expect(api.post).toHaveBeenCalledWith('/start-discovery', payload)
  })

  it('getJob fetches the standalone job resource', () => {
    getJob('job-1')
    expect(api.get).toHaveBeenCalledWith('/discovery-jobs/job-1')
  })

  it('getDiscoveryRun fetches the run resource', () => {
    getDiscoveryRun('run-1')
    expect(api.get).toHaveBeenCalledWith('/discovery-runs/run-1')
  })

  it('stopDiscoveryRun posts to the stop endpoint with no body', () => {
    stopDiscoveryRun('run-1')
    expect(api.post).toHaveBeenCalledWith('/discovery-runs/run-1/stop')
  })

  it('stopDiscoveryJob posts to the job stop endpoint', () => {
    stopDiscoveryJob('job-1')
    expect(api.post).toHaveBeenCalledWith('/discovery-jobs/job-1/stop')
  })

  it('getJobEvents omits `after` on the first call', () => {
    getJobEvents('job-1', {})
    expect(api.get).toHaveBeenCalledWith('/discovery-jobs/job-1/events', { limit: 50 })
  })

  it('getJobEvents passes the cursor as `after` on subsequent calls', () => {
    getJobEvents('job-1', { after: 42, limit: 20 })
    expect(api.get).toHaveBeenCalledWith('/discovery-jobs/job-1/events', { after: 42, limit: 20 })
  })

  it('listDiscoveryRuns passes pagination params through', () => {
    listDiscoveryRuns({ page: 2, page_size: 20 })
    expect(api.get).toHaveBeenCalledWith('/discovery-runs', { page: 2, page_size: 20 })
  })

  it('listDiscoveryJobs passes filter params through', () => {
    listDiscoveryJobs({ status: 'running', source: 'facebook', page: 1, page_size: 20 })
    expect(api.get).toHaveBeenCalledWith('/discovery-jobs', { status: 'running', source: 'facebook', page: 1, page_size: 20 })
  })
})
