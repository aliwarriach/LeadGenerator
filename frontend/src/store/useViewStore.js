import { create } from 'zustand'

// Only "identity" params are worth putting in the URL (deep-linkable, small,
// serializable). Handoff-only data like a freshly generated outreach draft
// stays in-memory — it's regenerated/refetched on a cold load anyway (see
// OutreachEditorView's draft-fallback effect).
const URL_PARAM_KEYS = ['leadId', 'runId', 'type']

// Keep in sync with the VIEWS map in App.jsx.
const KNOWN_VIEWS = new Set([
  'overview',
  'discovery',
  'businesses',
  'audit',
  'askai',
  'outreach-editor',
  'pipeline',
  'run-monitoring',
  'run-history',
  'job-queue',
])

function readUrlState() {
  const search = new URLSearchParams(window.location.search)
  const view = search.get('view')
  const params = {}
  for (const key of URL_PARAM_KEYS) {
    const value = search.get(key)
    if (value != null) params[key] = value
  }
  return { view: KNOWN_VIEWS.has(view) ? view : 'overview', params }
}

function buildUrl(view, params) {
  const search = new URLSearchParams()
  search.set('view', view)
  for (const key of URL_PARAM_KEYS) {
    if (params[key] != null) search.set(key, params[key])
  }
  return `${window.location.pathname}?${search.toString()}`
}

const initialState = readUrlState()

export const useViewStore = create((set) => ({
  view: initialState.view,
  breadcrumb: 'Workspace',
  params: initialState.params,
  setView: (view, breadcrumb = 'Workspace', params = {}) => {
    set({ view, breadcrumb, params })
    window.history.pushState({ view, params }, '', buildUrl(view, params))
  },
  // Applies browser back/forward navigation without pushing a new entry.
  _syncFromUrl: () => set({ ...readUrlState(), breadcrumb: 'Workspace' }),
}))

window.addEventListener('popstate', () => useViewStore.getState()._syncFromUrl())
// Normalize the URL on first load (e.g. bookmarked/typed link with no ?view=,
// or an unrecognized one) without creating an extra history entry.
window.history.replaceState({ view: initialState.view, params: initialState.params }, '', buildUrl(initialState.view, initialState.params))
