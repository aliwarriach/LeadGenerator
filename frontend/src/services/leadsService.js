import { api } from './api'

export function listLeads(params) {
  return api.get('/leads', params)
}

export function getLead(leadId) {
  return api.get(`/leads/${leadId}`)
}

export function updateLeadStage(leadId, stage) {
  return api.patch(`/leads/${leadId}/stage`, { stage })
}

// Live Groq call server-side (a few seconds, up to ~30s) — only ever fired
// from a deliberate button click, never on load/list render.
export function runAudit(leadId) {
  return api.post(`/leads/${leadId}/audit`)
}

export function getChatHistory(leadId) {
  return api.get(`/leads/${leadId}/chat`)
}

// Live Groq call server-side (a few seconds) — sends one message, gets one reply.
export function sendChatMessage(leadId, message) {
  return api.post(`/leads/${leadId}/chat`, { message })
}
