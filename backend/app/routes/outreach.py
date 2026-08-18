import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require
from app.core.permissions import Permission
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.outreach import (
    EmailGenerationResult,
    OutreachToneLiteral,
    ProposalGenerationResult,
    WhatsAppGenerationResult,
)
from app.services import outreach_service
from app.services.lead_service import LeadNotFoundError
from app.services.outreach_service import AiOutreachUnavailableError

router = APIRouter(prefix="/outreach", tags=["outreach"])


@router.post("/email/{lead_id}", response_model=EmailGenerationResult, dependencies=[Depends(require(Permission.OUTREACH_GENERATE))])
async def generate_email(
    lead_id: uuid.UUID,
    tone: OutreachToneLiteral = Query(default="default"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> EmailGenerationResult:
    """AI-generated personalized cold email, in the requested tone —
    grounded in the lead's real scraped data and AI audit results, not a
    generic template. Not persisted — each call regenerates fresh."""
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        try:
            return await outreach_service.generate_email(session, http_client, lead_id, settings, tone=tone)
        except LeadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AiOutreachUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/whatsapp/{lead_id}", response_model=WhatsAppGenerationResult, dependencies=[Depends(require(Permission.OUTREACH_GENERATE))])
async def generate_whatsapp(
    lead_id: uuid.UUID,
    tone: OutreachToneLiteral = Query(default="default"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> WhatsAppGenerationResult:
    """AI-generated short, direct WhatsApp outreach message, in the
    requested tone — grounded in the lead's real data. Not persisted."""
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        try:
            return await outreach_service.generate_whatsapp_message(
                session, http_client, lead_id, settings, tone=tone
            )
        except LeadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AiOutreachUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/proposal/{lead_id}", response_model=ProposalGenerationResult, dependencies=[Depends(require(Permission.OUTREACH_GENERATE))])
async def generate_proposal(
    lead_id: uuid.UUID,
    tone: OutreachToneLiteral = Query(default="default"),
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ProposalGenerationResult:
    """AI-generated client-facing project proposal (problem analysis,
    proposed solution, pricing estimate, timeline, ROI justification), in
    the requested tone — grounded in the lead's real data. Not persisted."""
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        try:
            return await outreach_service.generate_proposal(session, http_client, lead_id, settings, tone=tone)
        except LeadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AiOutreachUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
