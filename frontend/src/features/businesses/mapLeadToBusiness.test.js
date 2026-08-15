import { describe, it, expect } from 'vitest'
import { mapLeadToBusiness } from './mapLeadToBusiness'

function makeLead(overrides = {}) {
  return {
    id: 'lead-1',
    name: 'Acme Dental',
    category: 'Dental Clinic',
    search_location: 'Dubai, UAE',
    rating: 4.5,
    has_website: true,
    website: 'https://www.acmedental.com/book',
    website_domain: 'acmedental.com',
    website_score: 82,
    pipeline_stage: 'new_lead',
    ai_audited_at: null,
    ...overrides,
  }
}

describe('mapLeadToBusiness', () => {
  it('displays the bare domain but builds the href from the full URL', () => {
    const business = mapLeadToBusiness(makeLead())
    expect(business.website).toBe('acmedental.com')
    expect(business.websiteHref).toBe('https://www.acmedental.com/book')
  })

  it('adds a scheme to the href when the stored website is missing one', () => {
    const business = mapLeadToBusiness(makeLead({ website: 'www.acmedental.com/book', website_domain: null }))
    expect(business.website).toBe('www.acmedental.com/book')
    expect(business.websiteHref).toBe('https://www.acmedental.com/book')
  })

  it('falls back to website_domain for the href when the full website is missing', () => {
    const business = mapLeadToBusiness(makeLead({ website: null, website_domain: 'acmedental.com' }))
    expect(business.websiteHref).toBe('https://acmedental.com')
  })

  it('leaves website and websiteHref null when the lead has no website', () => {
    const business = mapLeadToBusiness(makeLead({ has_website: false, website: 'https://acmedental.com', website_domain: 'acmedental.com' }))
    expect(business.website).toBeNull()
    expect(business.websiteHref).toBeNull()
  })

  it('carries through the pipeline stage', () => {
    const business = mapLeadToBusiness(makeLead({ pipeline_stage: 'contacted' }))
    expect(business.pipelineStage).toBe('contacted')
  })

  it('maps a completed audit', () => {
    const business = mapLeadToBusiness(
      makeLead({
        ai_audited_at: '2026-08-01T00:00:00Z',
        ai_ui_score: 7,
        ai_conversion_score: 6,
        ai_content_score: 8,
        ai_trust_score: 9,
        ai_issues: ['Slow load time'],
        ai_summary: 'Solid overall.',
      })
    )
    expect(business.audit).toEqual({
      uiScore: 7,
      conversionScore: 6,
      contentScore: 8,
      trustScore: 9,
      issues: ['Slow load time'],
      summary: 'Solid overall.',
      auditedAt: '2026-08-01T00:00:00Z',
    })
  })
})
