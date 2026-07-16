import { describe, it, expect } from 'vitest'
import { sectionsToContent, contentToSections } from './proposalSections'
import { PROPOSAL_SECTION_HEADINGS } from '../../constants/askai'

describe('sectionsToContent', () => {
  it('flattens sections into markdown headings joined by blank lines', () => {
    const sections = [
      { heading: 'Problem Analysis', content: 'They lack online booking.' },
      { heading: 'Proposed Solution', content: 'Add a booking widget.' },
    ]
    expect(sectionsToContent(sections)).toBe(
      '## Problem Analysis\n\nThey lack online booking.\n\n## Proposed Solution\n\nAdd a booking widget.'
    )
  })
})

describe('contentToSections', () => {
  it('round-trips through sectionsToContent', () => {
    const sections = [
      { heading: 'Problem Analysis', content: 'They lack online booking.' },
      { heading: 'Proposed Solution', content: 'Add a booking widget.' },
    ]
    expect(contentToSections(sectionsToContent(sections))).toEqual(sections)
  })

  it('returns 5 empty sections with fixed headings when content is empty', () => {
    const result = contentToSections('')
    expect(result).toHaveLength(5)
    expect(result.map((s) => s.heading)).toEqual(PROPOSAL_SECTION_HEADINGS)
    expect(result.every((s) => s.content === '')).toBe(true)
  })
})
