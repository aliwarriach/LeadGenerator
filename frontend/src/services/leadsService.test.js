import { describe, it, expect, vi } from 'vitest'
import { api } from './api'
import { listLeads, getLead, runAudit, getChatHistory, sendChatMessage, updateLeadStage } from './leadsService'

vi.mock('./api', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))

describe('leadsService', () => {
  it('listLeads passes params through', () => {
    listLeads({ page: 1, page_size: 50 })
    expect(api.get).toHaveBeenCalledWith('/leads', { page: 1, page_size: 50 })
  })

  it('getLead fetches the single lead resource', () => {
    getLead('lead-1')
    expect(api.get).toHaveBeenCalledWith('/leads/lead-1')
  })

  it('runAudit posts to the audit endpoint with no body', () => {
    runAudit('lead-1')
    expect(api.post).toHaveBeenCalledWith('/leads/lead-1/audit')
  })

  it('getChatHistory fetches the full chat history', () => {
    getChatHistory('lead-1')
    expect(api.get).toHaveBeenCalledWith('/leads/lead-1/chat')
  })

  it('sendChatMessage posts the message body', () => {
    sendChatMessage('lead-1', 'What should I pitch first?')
    expect(api.post).toHaveBeenCalledWith('/leads/lead-1/chat', { message: 'What should I pitch first?' })
  })

  it('updateLeadStage patches the stage endpoint', () => {
    updateLeadStage('lead-1', 'contacted')
    expect(api.patch).toHaveBeenCalledWith('/leads/lead-1/stage', { stage: 'contacted' })
  })
})
