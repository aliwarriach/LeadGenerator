import { api } from './api'

export function listLeads(params) {
  return api.get('/leads', params)
}

export function getLead(leadId) {
  return api.get(`/leads/${leadId}`)
}
