export const AUDIT_SUBJECT = {
  breadcrumb: 'Businesses / Pearl Dental Clinic',
  business: 'Pearl Dental Clinic',
  version: 'v2 · today',
  domain: 'pearldentaldubai.ae',
}

export const AUDIT_OVERALL = {
  score: 58,
  max: 100,
  formulaLines: ['60% Lighthouse hard metrics', '40% AI qualitative · formula v1'],
}

export const LIGHTHOUSE_METRICS = [
  { label: 'Performance', value: 41 },
  { label: 'SEO', value: 68 },
  { label: 'Accessibility', value: 79 },
  { label: 'Best practices', value: 83 },
]
export const LIGHTHOUSE_SOURCE = 'Source: Google Lighthouse (PageSpeed Insights) — never AI-estimated'

export const AI_METRICS = [
  { label: 'UI / UX', value: 66 },
  { label: 'Conversion', value: 38 },
  { label: 'Content', value: 52 },
  { label: 'Trust signals', value: 74 },
]
export const AI_METRICS_SOURCE = 'Source: LLM analysis of extracted page structure · claude-sonnet-4-6'

export const AI_SUMMARY = {
  text: "The site presents well visually but leaks conversions: no online booking despite 80% of competitors offering it, the phone number isn't tap-to-call on mobile, and the contact form has 9 fields. Content is thin on service pages (~120 words each), hurting SEO for high-intent terms like \"veneers Dubai\". Trust signals exist (DHA license, reviews) but are buried in the footer. Performance regression since v1 traces to an unoptimized 4.2MB hero video.",
  services: ['Online booking system', 'Performance rescue', 'Service-page SEO content', 'Mobile CRO pass'],
}

export const KEY_ISSUES = [
  { severity: 'High', text: '4.2MB autoplay hero video — LCP 6.8s on mobile (Lighthouse)' },
  { severity: 'High', text: 'No online booking — every appointment requires a phone call' },
  { severity: 'Med', text: 'Missing meta descriptions on 7 of 12 pages (Lighthouse SEO)' },
  { severity: 'Med', text: 'Contact form: 9 required fields, no validation feedback' },
  { severity: 'Low', text: 'DHA license + 480 reviews buried in footer — surface above fold' },
]

export const RECOMMENDATIONS = [
  'Replace hero video with optimized poster + click-to-play — est. LCP 6.8s → 2.1s',
  'Add booking widget (Zoho Bookings / custom) — est. +15–25% appointment volume',
  'Rewrite 12 service pages to 500+ words targeting "treatment + Dubai" keywords',
  'Cut form to 3 fields, add WhatsApp CTA — standard for UAE patients',
  'Move trust bar (DHA · 4.8★ · 480 reviews) directly under hero',
]

export const REANALYZE_TOAST = 'Re-analysis queued — a new audit version will appear when done'
export const EXPORT_PDF_TOAST = 'PDF report generating — check exports in a moment'
