import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Tracks the most recent non-terminal discovery run so the user can always
// get back to it (e.g. after navigating away) — persisted so it survives a
// page refresh too. Cleared automatically once that run reaches a terminal
// status (see useDiscoveryRun).
export const useActiveRunStore = create(
  persist(
    (set) => ({
      activeRunId: null,
      setActiveRunId: (runId) => set({ activeRunId: runId }),
      clearActiveRunId: () => set({ activeRunId: null }),
    }),
    { name: 'lead-gen-active-run' }
  )
)
