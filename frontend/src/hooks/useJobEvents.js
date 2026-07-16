import { useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getJobEvents } from '../services/discoveryService'
import { getErrorMessage } from '../services/api'

const EVENTS_POLL_MS = 1500

// Only meant to be mounted while a job's log panel is expanded/visible —
// callers should unmount this (not just pass enabled: false) for off-screen jobs.
export function useJobEvents(jobId, { enabled = true } = {}) {
  const cursorRef = useRef(undefined)
  const queryClient = useQueryClient()

  return useQuery({
    queryKey: ['job-events', jobId],
    queryFn: async () => {
      const response = await getJobEvents(jobId, { after: cursorRef.current })
      if (!response.ok) {
        throw new Error(getErrorMessage(response, 'Failed to load job log'))
      }
      // next_cursor is a bookmark, not a "has more" flag — a null value means
      // "keep reusing the last cursor," not "stop polling."
      if (response.data.next_cursor != null) {
        cursorRef.current = response.data.next_cursor
      }
      const previousItems = queryClient.getQueryData(['job-events', jobId])?.items ?? []
      return { items: [...previousItems, ...response.data.items], next_cursor: cursorRef.current }
    },
    enabled: enabled && Boolean(jobId),
    refetchInterval: enabled ? EVENTS_POLL_MS : false,
  })
}
