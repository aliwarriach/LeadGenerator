import { create } from 'zustand'

export const useViewStore = create((set) => ({
  view: 'overview',
  breadcrumb: 'Workspace',
  setView: (view, breadcrumb = 'Workspace') => set({ view, breadcrumb }),
}))
