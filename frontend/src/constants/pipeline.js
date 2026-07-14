export const PIPELINE_STAGES = [
  { id: 'new', label: 'NEW', color: '#5aa9f7' },
  { id: 'contacted', label: 'CONTACTED', color: '#f0b429' },
  { id: 'qualified', label: 'QUALIFIED', color: '#a78bfa' },
  { id: 'proposal', label: 'PROPOSAL', color: '#3ecf8e' },
  { id: 'won', label: 'WON', color: '#2da572' },
]

export const PIPELINE_CARDS = [
  { id: '1', name: 'Al Noor Dental Center', meta: 'Sharjah · no website', value: '$4,200', stage: 'new' },
  { id: '2', name: 'Gulf Family Dentistry', meta: 'Sharjah · no website', value: '$3,500', stage: 'new' },
  { id: '3', name: 'Ivory Dental Lounge', meta: 'Downtown · score 72', value: '$6,000', stage: 'new' },
  { id: '4', name: 'Smile Studio Marina', meta: 'Marina · score 64', value: '$5,800', stage: 'contacted' },
  { id: '5', name: 'City Smiles Clinic', meta: 'Deira · no website', value: '$3,200', stage: 'contacted' },
  { id: '6', name: 'Pearl Dental Clinic', meta: 'Marina · score 58', value: '$8,400', stage: 'qualified' },
  { id: '7', name: 'Al Noor Med Spa', meta: 'JBR · score 51', value: '$7,600', stage: 'qualified' },
  { id: '8', name: 'Denta Prime', meta: 'Business Bay · score 47', value: '$9,500', stage: 'proposal' },
  { id: '9', name: 'GreenLeaf Landscaping', meta: 'Website + SEO retainer', value: '$3,800', stage: 'won' },
]

export const PIPELINE_TOTAL_VALUE = '$46,200 in play'
