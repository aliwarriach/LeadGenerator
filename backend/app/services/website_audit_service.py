import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.enrichers import groq_enricher, website_content_enricher
from app.repositories import lead_repository
from app.schemas.website_audit import LeadAuditResponse
from app.services.lead_service import LeadNotFoundError

logger = logging.getLogger(__name__)


class LeadHasNoWebsiteError(Exception):
    pass


class AiAuditUnavailableError(Exception):
    pass


async def audit_lead_website(
    session: AsyncSession, http_client: httpx.AsyncClient, lead_id: uuid.UUID, settings: Settings
) -> LeadAuditResponse:
    """Runs the on-demand AI website audit for one lead: fetch its page
    content, ask Groq to evaluate it against the lead's existing PageSpeed
    scores, and persist the result.

    Deliberately not part of enrich_lead()'s automatic pipeline — an LLM
    call per lead is real cost that shouldn't be spent on every scraped lead
    regardless of whether anyone reviews it; this only runs when explicitly
    requested via POST /leads/{id}/audit.
    """
    lead = await lead_repository.get_by_id(session, lead_id)
    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")
    if not lead.website:
        raise LeadHasNoWebsiteError(f"Lead {lead_id} has no website to audit")
    if not settings.groq_api_key:
        raise AiAuditUnavailableError("Groq API key not configured")

    content = await website_content_enricher.extract_content(
        http_client,
        lead.website,
        fetch_timeout_seconds=settings.website_content_fetch_timeout_seconds,
        max_chars=settings.website_content_max_chars,
    )

    result = await groq_enricher.evaluate_website(
        http_client,
        lead.website,
        pagespeed_scores=lead.website_score_details,
        content=content,
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
    )
    if result is None:
        raise AiAuditUnavailableError(f"AI audit failed for lead {lead_id} — Groq request or response was unusable")

    updated = await lead_repository.update_ai_audit(session, lead_id, result)
    if updated is None:
        # Lead existed moments ago but is gone now (e.g. concurrent delete) —
        # genuinely exceptional, not a normal not-found path.
        logger.error("Lead %s vanished between audit read and persist", lead_id)
        raise LeadNotFoundError(f"Lead {lead_id} not found")

    return LeadAuditResponse(
        lead_id=updated.id,
        ui_score=updated.ai_ui_score,
        conversion_score=updated.ai_conversion_score,
        content_score=updated.ai_content_score,
        trust_score=updated.ai_trust_score,
        issues=updated.ai_issues,
        summary=updated.ai_summary,
        audited_at=updated.ai_audited_at,
    )
