// The table displays the short bare domain (website_domain) for readability,
// but that string is unsafe to use directly as an <a href> — it would
// resolve as a relative link. Build the real navigable URL from the full
// `website` column instead, defensively adding a scheme if one is somehow
// missing (the backend normalizer always adds one, but this field can also
// come from older/raw-imported rows).
function toHref(url) {
  if (!url) return null
  return /^https?:\/\//i.test(url) ? url : `https://${url}`
}

export function mapLeadToBusiness(lead) {
  return {
    id: lead.id,
    name: lead.name,
    category: lead.category ?? lead.search_location ?? 'Uncategorized',
    rating: lead.rating,
    website: lead.has_website ? lead.website_domain || lead.website : null,
    websiteHref: lead.has_website ? toHref(lead.website || lead.website_domain) : null,
    score: lead.website_score,
    hasWebsite: Boolean(lead.has_website),
    pipelineStage: lead.pipeline_stage,
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
