import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import dashboard_repository
from app.schemas.dashboard import (
    DashboardActivityEntry,
    DashboardActivityResponse,
    DashboardStatsResponse,
    DiscoveryVolumeDay,
    DiscoveryVolumeResponse,
    LeadStageMixEntry,
    LeadStageMixResponse,
)
from app.services.lead_service import LeadServiceUnavailableError

logger = logging.getLogger(__name__)


async def get_stats(session: AsyncSession) -> DashboardStatsResponse:
    try:
        stats = await dashboard_repository.get_stats(session)
    except Exception as exc:
        logger.error("Failed to compute dashboard stats", exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc
    return DashboardStatsResponse(**stats)


async def get_discovery_volume(session: AsyncSession, *, days: int) -> DiscoveryVolumeResponse:
    try:
        rows = await dashboard_repository.get_discovery_volume(session, days=days)
    except Exception as exc:
        logger.error("Failed to compute discovery volume", exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    day_entries = [DiscoveryVolumeDay(**row) for row in rows]
    total = sum(d.has_website + d.no_website for d in day_entries)
    return DiscoveryVolumeResponse(days=day_entries, total=total)


async def get_lead_stage_mix(session: AsyncSession) -> LeadStageMixResponse:
    try:
        rows = await dashboard_repository.get_lead_stage_mix(session)
    except Exception as exc:
        logger.error("Failed to compute lead stage mix", exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    items = [LeadStageMixEntry(**row) for row in rows]
    return LeadStageMixResponse(items=items, total=sum(i.count for i in items))


async def list_recent_activity(session: AsyncSession, *, limit: int) -> DashboardActivityResponse:
    try:
        rows = await dashboard_repository.list_recent_activity(session, limit=limit)
    except Exception as exc:
        logger.error("Failed to list recent activity", exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc
    return DashboardActivityResponse(items=[DashboardActivityEntry(**row) for row in rows])
