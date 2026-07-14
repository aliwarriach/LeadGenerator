import { Search, Sparkles, BarChart3, ArrowRight, CircleCheck } from 'lucide-react'

export const STATS = [
  { key: 'discovered', label: 'Businesses discovered', value: '1,284', delta: '▲ 212 this week', deltaTone: 'signal' },
  { key: 'hot', label: 'No website — hot leads', value: '341', valueTone: 'amber', delta: '26.6% of total', deltaTone: 'muted' },
  { key: 'audits', label: 'Audits completed', value: '876', delta: '▲ 118 this week', deltaTone: 'signal' },
  { key: 'pipeline', label: 'Pipeline value', value: '$46.2k', delta: '14 active deals', deltaTone: 'muted' },
]

export const DISCOVERY_VOLUME = [
  { day: 'Mon', hasWebsite: 110, noWebsite: 38 },
  { day: 'Tue', hasWebsite: 150, noWebsite: 52 },
  { day: 'Wed', hasWebsite: 95, noWebsite: 30 },
  { day: 'Thu', hasWebsite: 180, noWebsite: 61 },
  { day: 'Fri', hasWebsite: 205, noWebsite: 74 },
  { day: 'Sat', hasWebsite: 88, noWebsite: 25 },
  { day: 'Sun', hasWebsite: 144, noWebsite: 47 },
]
export const DISCOVERY_VOLUME_TOTAL = '1,284 total'

export const LEAD_STAGE_MIX = [
  { stage: 'New', count: 68, color: '#5aa9f7' },
  { stage: 'Contacted', count: 41, color: '#f0b429' },
  { stage: 'Qualified', count: 19, color: '#a78bfa' },
  { stage: 'Proposal', count: 9, color: '#3ecf8e' },
  { stage: 'Won', count: 5, color: '#2da572' },
]

export const ACTIVITY_FEED = [
  {
    id: 1,
    icon: Search,
    tone: 'signal',
    time: '12 min ago',
    text: '**Discovery finished** — 96 dental clinics in Dubai & Sharjah, 31 without websites',
  },
  {
    id: 2,
    icon: Sparkles,
    tone: 'violet',
    time: '1 hr ago',
    text: '**Proposal generated** for Pearl Dental Clinic — booking system + new website',
  },
  {
    id: 3,
    icon: BarChart3,
    tone: 'blue',
    time: '3 hrs ago',
    text: '**Audit v2 completed** — Smile Studio Marina scored 58/100 (perf regressed −9)',
  },
  {
    id: 4,
    icon: ArrowRight,
    tone: 'amber',
    time: 'Yesterday',
    text: '**Al Noor Med Spa** moved to **Qualified** by Jawad',
  },
  {
    id: 5,
    icon: CircleCheck,
    tone: 'signal',
    time: '2 days ago',
    text: '**Deal won** — GreenLeaf Landscaping, $3,800 website + SEO retainer',
  },
]
