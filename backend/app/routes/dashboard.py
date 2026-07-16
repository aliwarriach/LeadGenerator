from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.dashboard import (
    DashboardActivityResponse,
    DashboardStatsResponse,
    DiscoveryVolumeResponse,
    LeadStageMixResponse,
)
from app.services import dashboard_service
from app.services.lead_service import LeadServiceUnavailableError

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStatsResponse)
async def get_stats(session: AsyncSession = Depends(get_db_session)) -> DashboardStatsResponse:
    try:
        return await dashboard_service.get_stats(session)
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/discovery-volume", response_model=DiscoveryVolumeResponse)
async def get_discovery_volume(
    days: int = Query(default=7, ge=1, le=90),
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryVolumeResponse:
    try:
        return await dashboard_service.get_discovery_volume(session, days=days)
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/lead-stage-mix", response_model=LeadStageMixResponse)
async def get_lead_stage_mix(session: AsyncSession = Depends(get_db_session)) -> LeadStageMixResponse:
    try:
        return await dashboard_service.get_lead_stage_mix(session)
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/activity", response_model=DashboardActivityResponse)
async def list_recent_activity(
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardActivityResponse:
    try:
        return await dashboard_service.list_recent_activity(session, limit=limit)
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
