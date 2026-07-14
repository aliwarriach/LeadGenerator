import { LayoutDashboard, Search, Building2, Kanban, ShieldCheck, Sparkles } from 'lucide-react'

export const NAV_SECTIONS = [
  {
    label: 'Workspace',
    items: [
      { id: 'overview', label: 'Overview', icon: LayoutDashboard },
      { id: 'discovery', label: 'Discovery', icon: Search },
      { id: 'businesses', label: 'Businesses', icon: Building2 },
      { id: 'pipeline', label: 'Pipeline', icon: Kanban },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { id: 'audit', label: 'Audit Report', icon: ShieldCheck },
      { id: 'askai', label: 'Ask AI', icon: Sparkles },
    ],
  },
]

export const WORKSPACE_USER = { name: 'Haseeb', org: 'Amperor · Pro plan' }
