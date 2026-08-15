import { describe, it, expect } from 'vitest'
import {
  formatAvgDuration,
  formatAvgLeadsSaved,
  formatCompletedRunCount,
  formatSuccessRate,
  formatTotalLeadsSaved,
} from './formatRunStats'

describe('formatAvgDuration', () => {
  it('returns null when there is no data', () => {
    expect(formatAvgDuration(null)).toBe(null)
  })

  it('formats sub-minute durations as seconds', () => {
    expect(formatAvgDuration(45)).toBe('45s')
  })

  it('formats minute-scale durations', () => {
    expect(formatAvgDuration(245)).toBe('4 minutes')
  })

  it('formats hour-scale durations', () => {
    expect(formatAvgDuration(3725)).toBe('1 hour 2 minutes')
  })
})

describe('formatAvgLeadsSaved', () => {
  it('returns null when there is no data', () => {
    expect(formatAvgLeadsSaved(null)).toBe(null)
  })

  it('rounds to the nearest whole lead', () => {
    expect(formatAvgLeadsSaved(12.4)).toBe('~12')
    expect(formatAvgLeadsSaved(12.6)).toBe('~13')
  })
})

describe('formatCompletedRunCount', () => {
  it('handles zero honestly', () => {
    expect(formatCompletedRunCount(0)).toBe('No completed runs yet')
  })

  it('uses singular for exactly one run', () => {
    expect(formatCompletedRunCount(1)).toBe('1 completed run')
  })

  it('uses plural for multiple runs', () => {
    expect(formatCompletedRunCount(7)).toBe('7 completed runs')
  })
})

describe('formatSuccessRate', () => {
  it('returns null when there is no data', () => {
    expect(formatSuccessRate(null)).toBe(null)
  })

  it('formats a fraction as a rounded percentage', () => {
    expect(formatSuccessRate(0.75)).toBe('75%')
    expect(formatSuccessRate(1)).toBe('100%')
    expect(formatSuccessRate(0)).toBe('0%')
  })
})

describe('formatTotalLeadsSaved', () => {
  it('returns null when there is no data', () => {
    expect(formatTotalLeadsSaved(null)).toBe(null)
  })

  it('pluralizes correctly', () => {
    expect(formatTotalLeadsSaved(1)).toBe('1 lead')
    expect(formatTotalLeadsSaved(0)).toBe('0 leads')
    expect(formatTotalLeadsSaved(1234)).toBe('1,234 leads')
  })
})
