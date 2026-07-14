import { Mail, Briefcase, MessageCircle, FileText, Settings2 } from 'lucide-react'

export const CHAT_SUBJECT = {
  breadcrumb: 'Businesses / Pearl Dental Clinic',
  title: 'Pearl Dental Clinic — assistant',
  context: 'Context: business profile · audit v2 · 3 saved notes',
}

export const INITIAL_MESSAGES = [
  { id: 1, role: 'user', blocks: [{ type: 'p', text: 'What services should I pitch them first?' }] },
  {
    id: 2,
    role: 'assistant',
    blocks: [
      {
        type: 'p',
        text: "Based on audit v2, lead with the **online booking system** — it's their biggest revenue leak. 80% of nearby competitors offer booking; they don't, and their 480 reviews prove demand. Bundle it with:",
      },
      {
        type: 'ul',
        items: [
          '**Performance rescue** (6.8s LCP is losing mobile patients before the page loads)',
          '**WhatsApp CTA integration** — standard patient behavior in UAE',
        ],
      },
      { type: 'p', text: 'Position SEO content as phase 2 so the first invoice stays small and fast to approve.' },
    ],
  },
  { id: 3, role: 'user', blocks: [{ type: 'p', text: "What's a realistic budget range for them?" }] },
  {
    id: 4,
    role: 'assistant',
    blocks: [
      {
        type: 'p',
        text: "They're a mid-size clinic (2 branches, 480 reviews, DHA-licensed) — likely **AED 15k–30k** comfort zone for a first project. Suggested framing: booking + performance fix at **AED 12,500**, positioned against the cost of ~10 lost patients/month. Keeps you under their approval threshold while opening the retainer door.",
      },
    ],
  },
]

export const AI_REPLIES = [
  'Their likely stack is WordPress + Elementor (theme hints in audit extraction). Migration friction is low — you can pitch improvements without a full rebuild, which keeps the proposal cheap and the close fast.',
  'Best opener angle: the 480 reviews. Something like — "you\'ve clearly earned patient trust; your website just isn\'t converting it." Specific, complimentary, and points straight at the booking gap.',
  'Decision maker is likely the practice owner or clinic manager. UAE clinics respond well to WhatsApp-first outreach; email second, LinkedIn third.',
]

export const OUTREACH_ACTIONS = [
  { id: 'email', icon: Mail, label: 'Cold email', toast: '**Cold email** drafted — saved to Outreach Assets' },
  { id: 'linkedin', icon: Briefcase, label: 'LinkedIn message', toast: '**LinkedIn message** drafted — copy & send manually' },
  { id: 'whatsapp', icon: MessageCircle, label: 'WhatsApp / cold message', toast: '**WhatsApp opener** drafted — saved to Outreach Assets' },
  { id: 'proposal', icon: FileText, label: 'Full proposal', toast: '**Proposal** generating — booking system + perf rescue, AED 12,500' },
  { id: 'estimate', icon: Settings2, label: 'Cost + complexity estimate', toast: '**Estimate**: booking integration ≈ 3–4 wks, medium complexity' },
]

export const GROUNDING_CONTEXT =
  'Dental clinic · Dubai Marina + JLT · 4.8★ (480) · site score 58/100 · top gap: no online booking · decision maker unknown'
