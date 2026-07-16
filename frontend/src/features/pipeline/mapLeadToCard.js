export function mapLeadToCard(lead) {
  const meta = [
    lead.search_location ?? lead.location,
    lead.has_website ? (lead.website_score != null ? `score ${Math.round(lead.website_score)}` : null) : 'no website',
  ]
    .filter(Boolean)
    .join(' · ')

  return {
    id: lead.id,
    name: lead.name,
    meta,
    stage: lead.pipeline_stage,
    revenueLevel: lead.estimated_revenue_level,
  }
}
