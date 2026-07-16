import { api } from './api'

// Ephemeral — regenerates fresh from Groq every call, never persisted server-side.
export function generateEmail(leadId, tone) {
  return api.post(`/outreach/email/${leadId}`, {}, { params: { tone } })
}

export function generateWhatsapp(leadId, tone) {
  return api.post(`/outreach/whatsapp/${leadId}`, {}, { params: { tone } })
}

export function generateProposal(leadId, tone) {
  return api.post(`/outreach/proposal/${leadId}`, {}, { params: { tone } })
}

export function getOutreachDraft(leadId, type) {
  return api.get(`/outreach-drafts/${leadId}`, { type })
}

export function saveOutreachDraft(leadId, type, payload) {
  return api.post(`/outreach-drafts/${leadId}`, payload, { params: { type } })
}

export function updateOutreachDraft(draftId, payload) {
  return api.patch(`/outreach-drafts/${draftId}`, payload)
}

// Binary PDF response — caller must set responseType: 'blob'.
export function generateProposalPdf(draftId) {
  return api.post(`/outreach-drafts/${draftId}/pdf`, {}, { responseType: 'blob' })
}
