import { useCallback, useState } from 'react'
import { startDiscovery } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

export function useDiscovery() {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  const runDiscovery = useCallback(async (payload) => {
    setRunning(true)
    setError(null)
    try {
      const response = await startDiscovery(payload)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to start discovery'))
      }
      return response.data // { ...echo, run_id, jobs }
    } catch (err) {
      setError(err.message)
      throw err
    } finally {
      setRunning(false)
    }
  }, [])

  return { runDiscovery, running, error }
}
