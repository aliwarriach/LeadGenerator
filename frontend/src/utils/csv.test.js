import { describe, it, expect } from 'vitest'
import { businessesToCsv } from './csv'

describe('businessesToCsv', () => {
  it('builds a header row plus one row per business', () => {
    const csv = businessesToCsv([
      { name: 'Acme Dental', category: 'Dental Clinic', rating: 4.5, website: 'acme.com', score: 82, pipelineStage: 'new_lead' },
    ])
    const lines = csv.split('\r\n')
    expect(lines[0]).toBe('Name,Category,Rating,Website,Score,Pipeline Stage')
    expect(lines[1]).toBe('Acme Dental,Dental Clinic,4.5,acme.com,82,new_lead')
  })

  it('quotes and escapes fields containing commas, quotes, or newlines', () => {
    const csv = businessesToCsv([
      { name: 'Bob\'s "Best" Dental, LLC', category: 'Dental\nClinic', rating: null, website: null, score: null, pipelineStage: null },
    ])
    const lines = csv.split('\r\n')
    expect(lines[1]).toBe('"Bob\'s ""Best"" Dental, LLC","Dental\nClinic",,,,')
  })

  it('produces only the header row for an empty list', () => {
    const csv = businessesToCsv([])
    expect(csv).toBe('Name,Category,Rating,Website,Score,Pipeline Stage')
  })
})
