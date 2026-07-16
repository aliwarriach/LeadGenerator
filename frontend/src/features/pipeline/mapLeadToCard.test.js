import { describe, it, expect } from 'vitest'
import { mapLeadToCard } from './mapLeadToCard'

describe('mapLeadToCard', () => {
  it('shows website score in the meta line when the lead has a website', () => {
    const card = mapLeadToCard({
      id: '1',
      name: 'Pearl Dental Clinic',
      search_location: 'Marina',
      location: null,
      has_website: true,
      website_score: 58.4,
      pipeline_stage: 'qualified',
      estimated_revenue_level: '10k-50k/mo',
    })
    expect(card.meta).toBe('Marina · score 58')
    expect(card.stage).toBe('qualified')
    expect(card.revenueLevel).toBe('10k-50k/mo')
  })

  it('shows "no website" when the lead has none', () => {
    const card = mapLeadToCard({
      id: '2',
      name: 'Al Noor Dental Center',
      search_location: null,
      location: 'Sharjah',
      has_website: false,
      website_score: null,
      pipeline_stage: 'new_lead',
      estimated_revenue_level: null,
    })
    expect(card.meta).toBe('Sharjah · no website')
    expect(card.revenueLevel).toBeNull()
  })
})
