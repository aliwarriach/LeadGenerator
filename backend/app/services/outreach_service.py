from __future__ import annotations

import logging
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.enrichers import groq_enricher
from app.models.lead import Lead
from app.repositories import lead_repository
from app.schemas.outreach import EmailGenerationResult, ProposalGenerationResult, WhatsAppGenerationResult
from app.services.lead_context import build_lead_context
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError

logger = logging.getLogger(__name__)


class AiOutreachUnavailableError(Exception):
    pass


async def _get_lead_or_raise(session: AsyncSession, lead_id: uuid.UUID) -> Lead:
    try:
        lead = await lead_repository.get_by_id(session, lead_id)
    except Exception as exc:
        logger.error("Failed to fetch lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")
    return lead


async def generate_email(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    lead_id: uuid.UUID,
    settings: Settings,
    *,
    tone: str = "default",
) -> EmailGenerationResult:
    """On-demand cold email generation — not persisted, a fresh call
    regenerates rather than replaying a saved draft."""
    lead = await _get_lead_or_raise(session, lead_id)
    if not settings.groq_api_key:
        raise AiOutreachUnavailableError("Groq API key not configured")

    result = await groq_enricher.draft_cold_email(
        http_client,
        build_lead_context(lead),
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
        tone=tone,
        max_tokens=settings.groq_max_tokens,
    )
    if result is None:
        raise AiOutreachUnavailableError(f"AI email generation failed for lead {lead_id} — Groq request or response was unusable")
    return result


async def generate_whatsapp_message(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    lead_id: uuid.UUID,
    settings: Settings,
    *,
    tone: str = "default",
) -> WhatsAppGenerationResult:
    lead = await _get_lead_or_raise(session, lead_id)
    if not settings.groq_api_key:
        raise AiOutreachUnavailableError("Groq API key not configured")

    result = await groq_enricher.draft_whatsapp_message(
        http_client,
        build_lead_context(lead),
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
        tone=tone,
        max_tokens=settings.groq_max_tokens,
    )
    if result is None:
        raise AiOutreachUnavailableError(f"AI WhatsApp message generation failed for lead {lead_id} — Groq request or response was unusable")
    return result


async def generate_proposal(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    lead_id: uuid.UUID,
    settings: Settings,
    *,
    tone: str = "default",
) -> ProposalGenerationResult:
    lead = await _get_lead_or_raise(session, lead_id)
    if not settings.groq_api_key:
        raise AiOutreachUnavailableError("Groq API key not configured")

    result = await groq_enricher.draft_proposal(
        http_client,
        build_lead_context(lead),
        api_key=settings.groq_api_key,
        base_url=settings.groq_base_url,
        model=settings.groq_model,
        timeout_seconds=settings.groq_timeout_seconds,
        max_retries=settings.groq_max_retries,
        tone=tone,
        max_tokens=settings.groq_max_tokens,
    )
    if result is None:
        raise AiOutreachUnavailableError(f"AI proposal generation failed for lead {lead_id} — Groq request or response was unusable")
    return result
