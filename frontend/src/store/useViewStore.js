import { create } from 'zustand'

export const useViewStore = create((set) => ({
  view: 'overview',
  breadcrumb: 'Workspace',
  params: {},
  setView: (view, breadcrumb = 'Workspace', params = {}) => set({ view, breadcrumb, params }),
}))
