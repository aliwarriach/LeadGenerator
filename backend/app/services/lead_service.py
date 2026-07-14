import logging
import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import lead_repository
from app.schemas.lead import LeadListResponse, LeadResponse, LeadSortBy, SortOrder

logger = logging.getLogger(__name__)


class LeadNotFoundError(Exception):
    pass


class LeadServiceUnavailableError(Exception):
    pass


async def list_leads(
    session: AsyncSession,
    *,
    source: str | None,
    has_website: bool | None,
    min_rating: float | None,
    min_website_score: float | None,
    name: str | None,
    search_location: str | None,
    niche: str | None,
    sort_by: LeadSortBy,
    sort_order: SortOrder,
    page: int,
    page_size: int,
) -> LeadListResponse:
    offset = (page - 1) * page_size
    try:
        leads, total = await lead_repository.list_leads(
            session,
            source=source,
            has_website=has_website,
            min_rating=min_rating,
            min_website_score=min_website_score,
            name_contains=name,
            search_location_contains=search_location,
            niche_equals=niche,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=page_size,
            offset=offset,
        )
    except Exception as exc:
        # Connection failures surface as raw driver/OS errors (e.g. ConnectionRefusedError),
        # not SQLAlchemyError, since SQLAlchemy only wraps errors after a connection exists.
        logger.error("Failed to list leads", exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    total_pages = math.ceil(total / page_size) if total else 0

    return LeadListResponse(
        items=[LeadResponse.model_validate(lead) for lead in leads],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def get_lead(session: AsyncSession, lead_id: uuid.UUID) -> LeadResponse:
    try:
        lead = await lead_repository.get_by_id(session, lead_id)
    except Exception as exc:
        logger.error("Failed to fetch lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")
    return LeadResponse.model_validate(lead)
