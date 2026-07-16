import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityType
from app.repositories import activity_repository, lead_repository
from app.schemas.activity import ActivityListResponse, ActivityResponse
from app.schemas.lead import LeadResponse
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError

logger = logging.getLogger(__name__)


def _stage_label(stage: str) -> str:
    return stage.replace("_", " ").title()


async def change_lead_stage(session: AsyncSession, lead_id: uuid.UUID, stage: str) -> LeadResponse:
    """Sets Lead.pipeline_stage and logs a stage_change activity — the two
    always happen together, so this is one service call rather than a
    PATCH /leads/{id} + POST /activities/{id} pair the caller has to
    orchestrate."""
    try:
        lead = await lead_repository.update_lead_pipeline(
            session, lead_id, pipeline_stage=stage, estimated_revenue_level=None
        )
    except Exception as exc:
        logger.error("Failed to update pipeline stage for lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")

    try:
        await activity_repository.add_activity(
            session, lead_id, type=ActivityType.STAGE_CHANGE, description=f"Moved to {_stage_label(stage)}"
        )
    except Exception as exc:
        logger.error("Failed to log stage_change activity for lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    return LeadResponse.model_validate(lead)


async def create_activity(
    session: AsyncSession, lead_id: uuid.UUID, *, type: str, description: str
) -> ActivityResponse:
    try:
        lead = await lead_repository.get_by_id(session, lead_id)
    except Exception as exc:
        logger.error("Failed to fetch lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")

    try:
        activity = await activity_repository.add_activity(session, lead_id, type=type, description=description)
    except Exception as exc:
        logger.error("Failed to create activity for lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    return ActivityResponse.model_validate(activity)


async def list_activities(session: AsyncSession, lead_id: uuid.UUID) -> ActivityListResponse:
    try:
        lead = await lead_repository.get_by_id(session, lead_id)
    except Exception as exc:
        logger.error("Failed to fetch lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")

    try:
        activities = await activity_repository.list_by_lead(session, lead_id)
    except Exception as exc:
        logger.error("Failed to list activities for lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    return ActivityListResponse(
        lead_id=lead_id, items=[ActivityResponse.model_validate(a) for a in activities]
    )
