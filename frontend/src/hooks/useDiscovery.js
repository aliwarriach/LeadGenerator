import { useCallback, useState } from 'react'
import { startDiscovery, getJobStatus } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

const POLL_INTERVAL_MS = 2000
const MAX_POLL_ATTEMPTS = 45 // ~90s ceiling so a stuck worker can't hang the UI forever
const TERMINAL_STATUSES = new Set(['complete', 'not_found'])

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function pollJobsUntilDone(jobIds) {
  let latest = jobIds.map((jobId) => ({ jobId, status: 'queued' }))

  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    latest = await Promise.all(
      jobIds.map(async (jobId) => {
        const response = await getJobStatus(jobId)
        return response.ok ? { jobId, ...response.data } : { jobId, status: 'error' }
      })
    )

    if (latest.every((job) => TERMINAL_STATUSES.has(job.status) || job.status === 'error')) {
      return latest
    }

    await wait(POLL_INTERVAL_MS)
  }

  return latest
}

export function useDiscovery() {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  const runDiscovery = useCallback(async (payload) => {
    setRunning(true)
    setError(null)
    try {
      const startResponse = await startDiscovery(payload)
      if (!startResponse.ok) {
        throw new Error(getErrorMessage(startResponse, 'Failed to start discovery'))
      }

      const jobIds = startResponse.data.jobs.map((job) => job.job_id)
      const finalStatuses = await pollJobsUntilDone(jobIds)
      const succeeded = finalStatuses.filter((job) => job.status === 'complete' && job.success !== false).length

      if (succeeded === 0) {
        throw new Error('Discovery failed for every source — none of the scrapers completed successfully')
      }

      return { total: finalStatuses.length, succeeded }
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setRunning(false)
    }
  }, [])

  return { runDiscovery, running, error }
}
