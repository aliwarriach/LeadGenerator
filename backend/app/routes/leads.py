import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authz import require
from app.core.permissions import Permission
from app.core.config import Settings, get_settings
from app.db.session import get_db_session
from app.schemas.activity import StageUpdateRequest
from app.schemas.chat import ChatHistoryResponse, ChatMessageRequest, ChatMessageResponse
from app.schemas.lead import LeadListResponse, LeadResponse, LeadUpdateRequest
from app.schemas.website_audit import LeadAuditResponse
from app.services import activity_service, chat_service, lead_service, website_audit_service
from app.services.chat_service import AiChatUnavailableError
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.website_audit_service import AiAuditUnavailableError, LeadHasNoWebsiteError

router = APIRouter(tags=["leads"])


@router.get("/leads", response_model=LeadListResponse, dependencies=[Depends(require(Permission.LEADS_READ))])
async def list_leads(
    source: Literal["google_maps", "facebook", "serper"] | None = None,
    has_website: bool | None = None,
    min_rating: float | None = Query(default=None, ge=0, le=5),
    min_website_score: float | None = Query(default=None, ge=0, le=100),
    name: str | None = Query(default=None, max_length=256, description="Partial, case-insensitive match"),
    search_location: str | None = Query(default=None, max_length=512, description="Partial, case-insensitive match"),
    niche: str | None = Query(default=None, max_length=256, description="Exact match on the discovery custom_niche"),
    sort_by: Literal["created_at", "rating", "website_score", "name"] = "created_at",
    sort_order: Literal["asc", "desc"] = "desc",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> LeadListResponse:
    try:
        return await lead_service.list_leads(
            session,
            source=source,
            has_website=has_website,
            min_rating=min_rating,
            min_website_score=min_website_score,
            name=name,
            search_location=search_location,
            niche=niche,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/leads/{lead_id}", response_model=LeadResponse, dependencies=[Depends(require(Permission.LEADS_READ))])
async def get_lead(lead_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> LeadResponse:
    try:
        return await lead_service.get_lead(session, lead_id)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/leads/{lead_id}", response_model=LeadResponse, dependencies=[Depends(require(Permission.LEADS_WRITE))])
async def update_lead(
    lead_id: uuid.UUID,
    update: LeadUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Manually set CRM fields (pipeline_stage, estimated_revenue_level).
    Never touched by discovery/enrichment — re-scraping an existing lead
    does not reset these."""
    try:
        return await lead_service.update_lead(session, lead_id, update)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/leads/{lead_id}/stage", response_model=LeadResponse, dependencies=[Depends(require(Permission.PIPELINE_WRITE))])
async def update_lead_stage(
    lead_id: uuid.UUID,
    request: StageUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LeadResponse:
    """Moves a lead through the CRM pipeline and logs a stage_change
    activity — distinct from PATCH /leads/{id}, which patches CRM fields
    silently with no activity log entry."""
    try:
        return await activity_service.change_lead_stage(session, lead_id, request.stage)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/leads/{lead_id}/audit", response_model=LeadAuditResponse, dependencies=[Depends(require(Permission.AUDIT_RUN))])
async def audit_lead(
    lead_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> LeadAuditResponse:
    """On-demand AI website audit (Groq) — not run automatically during
    discovery, only when explicitly requested for a specific lead."""
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        try:
            return await website_audit_service.audit_lead_website(session, http_client, lead_id, settings)
        except LeadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except LeadHasNoWebsiteError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AiAuditUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/leads/{lead_id}/chat", response_model=ChatMessageResponse, dependencies=[Depends(require(Permission.LEADS_READ))])
async def chat_with_lead(
    lead_id: uuid.UUID,
    request: ChatMessageRequest,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ChatMessageResponse:
    """Contextual AI sales chatbot for one lead — full lead data + AI audit
    results injected as system context, conversation history persisted and
    replayed (bounded to the last N messages to respect Groq's free-tier
    rate limits)."""
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        try:
            return await chat_service.send_chat_message(session, http_client, lead_id, request.message, settings)
        except LeadNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except AiChatUnavailableError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/leads/{lead_id}/chat", response_model=ChatHistoryResponse, dependencies=[Depends(require(Permission.LEADS_READ))])
async def get_lead_chat_history(
    lead_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> ChatHistoryResponse:
    try:
        return await chat_service.get_chat_history(session, lead_id)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
