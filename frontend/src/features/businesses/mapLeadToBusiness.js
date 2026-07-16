export function mapLeadToBusiness(lead) {
  return {
    id: lead.id,
    name: lead.name,
    category: lead.category ?? lead.search_location ?? 'Uncategorized',
    rating: lead.rating,
    website: lead.has_website ? lead.website_domain || lead.website : null,
    score: lead.website_score,
    hasWebsite: Boolean(lead.has_website),
    audit:
      lead.ai_audited_at != null
        ? {
            uiScore: lead.ai_ui_score,
            conversionScore: lead.ai_conversion_score,
            contentScore: lead.ai_content_score,
            trustScore: lead.ai_trust_score,
            issues: lead.ai_issues ?? [],
            summary: lead.ai_summary,
            auditedAt: lead.ai_audited_at,
          }
        : null,
  }
}
