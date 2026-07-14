export function mapLeadToBusiness(lead) {
  return {
    id: lead.id,
    name: lead.name,
    category: lead.category ?? lead.search_location ?? 'Uncategorized',
    rating: lead.rating,
    website: lead.has_website ? lead.website_domain || lead.website : null,
    score: lead.website_score,
  }
}
