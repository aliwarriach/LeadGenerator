from app.models.lead import Lead


def build_lead_context(lead: Lead) -> str:
    """Formats a lead's scraped + AI-audit data as a text block for a Groq
    prompt. Shared by chat_service and outreach_service so both features
    describe the same lead identically."""
    lines = [
        f"Business name: {lead.name}",
        f"Category: {lead.category or 'unknown'}",
        f"Location: {lead.location or 'unknown'}",
        f"Website: {lead.website or 'none'}",
        f"Pipeline stage: {lead.pipeline_stage}",
    ]
    if lead.estimated_revenue_level:
        lines.append(f"Estimated revenue level: {lead.estimated_revenue_level}")
    if lead.website_score is not None:
        lines.append(f"Website quality score (0-100): {lead.website_score}")
    if lead.performance_issues:
        lines.append(f"Performance issues: {'; '.join(lead.performance_issues)}")
    if lead.ai_summary:
        lines.append(f"AI website audit summary: {lead.ai_summary}")
        lines.append(
            "AI audit scores (1-10) — "
            f"UI/UX: {lead.ai_ui_score}, Conversion: {lead.ai_conversion_score}, "
            f"Content: {lead.ai_content_score}, Trust: {lead.ai_trust_score}"
        )
    if lead.ai_issues:
        lines.append(f"AI-identified issues: {'; '.join(lead.ai_issues)}")
    return "\n".join(lines)
