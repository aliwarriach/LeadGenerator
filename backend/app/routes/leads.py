import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.lead import LeadListResponse, LeadResponse
from app.services import lead_service
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError

router = APIRouter(tags=["leads"])


@router.get("/leads", response_model=LeadListResponse)
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


@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(lead_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> LeadResponse:
    try:
        return await lead_service.get_lead(session, lead_id)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
