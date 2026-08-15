import { describe, it, expect } from 'vitest'
import { buildDiscoveryPayload } from './buildDiscoveryPayload'

const BASE = {
  countryId: 'uae',
  cityIds: ['uae-dubai'],
  customCity: '',
  industryIds: ['dental'],
  niche: '',
  filterIds: [],
}

describe('buildDiscoveryPayload', () => {
  it('builds a valid payload from chip selections', () => {
    const { payload, errors, fieldErrors } = buildDiscoveryPayload(BASE)
    expect(errors).toEqual([])
    expect(fieldErrors).toEqual({})
    expect(payload).toEqual({
      country: 'UAE',
      city: 'Dubai',
      custom_niche: 'Dental clinics',
    })
  })

  it('prefers a typed custom niche over selected industry chips', () => {
    const { payload } = buildDiscoveryPayload({ ...BASE, niche: 'orthodontists' })
    expect(payload.custom_niche).toBe('orthodontists')
  })

  it('merges chip cities and typed cities, deduping', () => {
    const { payload } = buildDiscoveryPayload({ ...BASE, customCity: 'Dubai, Al Ain' })
    expect(payload.city).toBe('Dubai, Al Ain')
  })

  it('adds min_rating only when the rating4 filter is active', () => {
    const withoutFilter = buildDiscoveryPayload(BASE)
    expect(withoutFilter.payload.min_rating).toBeUndefined()

    const withFilter = buildDiscoveryPayload({ ...BASE, filterIds: ['rating4'] })
    expect(withFilter.payload.min_rating).toBe(4.0)
  })

  it('returns a per-field error and null payload when no city is selected', () => {
    const { payload, errors, fieldErrors } = buildDiscoveryPayload({ ...BASE, cityIds: [] })
    expect(payload).toBeNull()
    expect(errors).toEqual(['Select or type at least one city.'])
    expect(fieldErrors).toEqual({ city: 'Select or type at least one city.' })
  })

  it('returns a per-field error when neither niche nor industry is set', () => {
    const { payload, fieldErrors } = buildDiscoveryPayload({ ...BASE, industryIds: [], niche: '' })
    expect(payload).toBeNull()
    expect(fieldErrors.niche).toBe('Enter a custom niche or select an industry.')
  })

  it('reports multiple field errors at once', () => {
    const { errors, fieldErrors } = buildDiscoveryPayload({ ...BASE, cityIds: [], industryIds: [], niche: '' })
    expect(errors).toHaveLength(2)
    expect(Object.keys(fieldErrors).sort()).toEqual(['city', 'niche'])
  })
})
