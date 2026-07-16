import { Mail, MessageCircle, FileText, ArrowRight } from 'lucide-react'

export const ACTIVITY_TYPE_META = {
  email: { icon: Mail, tone: 'blue', label: 'sent an email to' },
  whatsapp: { icon: MessageCircle, tone: 'signal', label: 'messaged' },
  proposal: { icon: FileText, tone: 'violet', label: 'generated a proposal for' },
  stage_change: { icon: ArrowRight, tone: 'amber', label: null },
}
