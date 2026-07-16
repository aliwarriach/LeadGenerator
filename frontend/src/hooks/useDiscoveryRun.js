import { useEffect, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getDiscoveryRun } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'
import { isTerminalStatus } from '../utils/statusMeta'
import { useActiveRunStore } from '../store/useActiveRunStore'

const ACTIVE_POLL_MS = 4000

// Extracted so the polling decision is a plain, testable function rather than
// buried inside the refetchInterval callback.
export function nextRunPollInterval(status) {
  if (!status || isTerminalStatus(status)) return false
  return ACTIVE_POLL_MS
}

export function useDiscoveryRun(runId) {
  const queryClient = useQueryClient()
  const wasTerminal = useRef(false)

  const query = useQuery({
    queryKey: ['discovery-run', runId],
    queryFn: async () => {
      const response = await getDiscoveryRun(runId)
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load run'))
      }
      return response.data
    },
    enabled: Boolean(runId),
    refetchInterval: (query) => nextRunPollInterval(query.state.data?.status),
  })

  useEffect(() => {
    const status = query.data?.status
    if (!status) return

    if (isTerminalStatus(status)) {
      if (!wasTerminal.current) {
        wasTerminal.current = true
        // Leads may have been saved even for blocked/stopped runs — refresh
        // the Businesses page's data once this run stops changing.
        queryClient.invalidateQueries({ queryKey: ['leads'] })
        // Only clear the "active run" pointer if it's still pointing at this
        // run — viewing an unrelated historical run must not wipe it out.
        if (useActiveRunStore.getState().activeRunId === runId) {
          useActiveRunStore.getState().clearActiveRunId()
        }
      }
    } else {
      wasTerminal.current = false
    }
  }, [query.data?.status, queryClient, runId])

  return query
}
