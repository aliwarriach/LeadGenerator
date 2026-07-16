import { describe, it, expect, vi } from 'vitest'
import { api } from './api'
import {
  generateEmail,
  generateWhatsapp,
  generateProposal,
  getOutreachDraft,
  saveOutreachDraft,
  updateOutreachDraft,
  generateProposalPdf,
} from './outreachService'

vi.mock('./api', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

describe('outreachService', () => {
  it('generateEmail posts to the email generation endpoint with tone as a query param', () => {
    generateEmail('lead-1', 'direct')
    expect(api.post).toHaveBeenCalledWith('/outreach/email/lead-1', {}, { params: { tone: 'direct' } })
  })

  it('generateWhatsapp posts to the whatsapp generation endpoint', () => {
    generateWhatsapp('lead-1', 'default')
    expect(api.post).toHaveBeenCalledWith('/outreach/whatsapp/lead-1', {}, { params: { tone: 'default' } })
  })

  it('generateProposal posts to the proposal generation endpoint', () => {
    generateProposal('lead-1', 'value_first')
    expect(api.post).toHaveBeenCalledWith('/outreach/proposal/lead-1', {}, { params: { tone: 'value_first' } })
  })

  it('getOutreachDraft fetches the draft filtered by type', () => {
    getOutreachDraft('lead-1', 'email')
    expect(api.get).toHaveBeenCalledWith('/outreach-drafts/lead-1', { type: 'email' })
  })

  it('saveOutreachDraft posts the draft body with type as a query param', () => {
    saveOutreachDraft('lead-1', 'email', { subject: 'Hi', content: 'Body' })
    expect(api.post).toHaveBeenCalledWith('/outreach-drafts/lead-1', { subject: 'Hi', content: 'Body' }, { params: { type: 'email' } })
  })

  it('updateOutreachDraft patches the draft by id', () => {
    updateOutreachDraft('draft-1', { subject: null, content: 'Updated' })
    expect(api.patch).toHaveBeenCalledWith('/outreach-drafts/draft-1', { subject: null, content: 'Updated' })
  })

  it('generateProposalPdf posts with a blob response type', () => {
    generateProposalPdf('draft-1')
    expect(api.post).toHaveBeenCalledWith('/outreach-drafts/draft-1/pdf', {}, { responseType: 'blob' })
  })
})
