import { Mail, MessageCircle, FileText } from 'lucide-react'

export const OUTREACH_TYPES = [
  { id: 'email', icon: Mail, label: 'Cold email' },
  { id: 'whatsapp', icon: MessageCircle, label: 'WhatsApp / cold message' },
  { id: 'proposal', icon: FileText, label: 'Full proposal' },
]

export const OUTREACH_TONES = [
  { id: 'default', label: 'Default' },
  { id: 'direct', label: 'More Direct' },
  { id: 'value_first', label: 'Value First' },
]

export const PROPOSAL_SECTION_HEADINGS = [
  'Problem Analysis',
  'Proposed Solution',
  'Pricing Estimate',
  'Timeline',
  'ROI Justification',
]
