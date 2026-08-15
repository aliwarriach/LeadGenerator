import { describe, it, expect, afterEach, vi } from 'vitest'

async function freshStore(url) {
  window.history.replaceState(null, '', url)
  vi.resetModules()
  const mod = await import('./useViewStore.js')
  return mod.useViewStore
}

describe('useViewStore', () => {
  afterEach(() => {
    window.history.replaceState(null, '', '/')
  })

  it('defaults to overview with no query string', async () => {
    const useViewStore = await freshStore('/')
    expect(useViewStore.getState().view).toBe('overview')
    expect(useViewStore.getState().params).toEqual({})
  })

  it('falls back to overview for an unrecognized ?view=', async () => {
    const useViewStore = await freshStore('/?view=not-a-real-view')
    expect(useViewStore.getState().view).toBe('overview')
  })

  it('hydrates view + identity params from the URL on load', async () => {
    const useViewStore = await freshStore('/?view=audit&leadId=abc-123')
    expect(useViewStore.getState().view).toBe('audit')
    expect(useViewStore.getState().params).toEqual({ leadId: 'abc-123' })
  })

  it('setView updates state and reflects identity params in the URL', async () => {
    const useViewStore = await freshStore('/')
    useViewStore.getState().setView('askai', 'Businesses / Acme', { leadId: 'lead-9' })
    expect(useViewStore.getState().view).toBe('askai')
    const search = new URLSearchParams(window.location.search)
    expect(search.get('view')).toBe('askai')
    expect(search.get('leadId')).toBe('lead-9')
  })

  it('does not leak non-identity params (e.g. a generated draft object) into the URL', async () => {
    const useViewStore = await freshStore('/')
    useViewStore.getState().setView('outreach-editor', 'Ask AI', {
      leadId: 'lead-9',
      type: 'email',
      generated: { subject: 'Hi', email_body: 'body' },
      breadcrumb: 'Businesses / Acme',
    })
    const search = new URLSearchParams(window.location.search)
    expect(search.get('leadId')).toBe('lead-9')
    expect(search.get('type')).toBe('email')
    expect(search.has('generated')).toBe(false)
    expect(search.has('breadcrumb')).toBe(false)
    // In-memory params still carry the full payload for the current session.
    expect(useViewStore.getState().params.generated).toEqual({ subject: 'Hi', email_body: 'body' })
  })

  it('syncs state back from the URL on browser back/forward (popstate)', async () => {
    const useViewStore = await freshStore('/')
    useViewStore.getState().setView('businesses')
    window.history.replaceState(null, '', '/?view=discovery')
    window.dispatchEvent(new PopStateEvent('popstate'))
    expect(useViewStore.getState().view).toBe('discovery')
  })
})
