import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Tracks the last business the user opened Audit/Ask AI for, independent of
// useViewStore's per-navigation params. Sidebar nav to 'audit'/'askai' passes
// no params (it's a generic tab switch), which would otherwise strand those
// screens on their empty state. Persisted so it survives a page refresh too.
export const useSelectedLeadStore = create(
  persist(
    (set) => ({
      selectedLeadId: null,
      setSelectedLeadId: (leadId) => set({ selectedLeadId: leadId }),
      clearSelectedLeadId: () => set({ selectedLeadId: null }),
    }),
    { name: 'lead-gen-selected-lead' }
  )
)
