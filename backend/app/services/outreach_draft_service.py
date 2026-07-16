import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outreach_draft import OutreachType
from app.repositories import activity_repository, lead_repository, outreach_draft_repository
from app.schemas.outreach_draft import OutreachDraftResponse
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.pdf_service import render_proposal_pdf

logger = logging.getLogger(__name__)

_ACTIVITY_DESCRIPTIONS = {
    OutreachType.EMAIL: "Email draft saved",
    OutreachType.WHATSAPP: "WhatsApp draft saved",
    OutreachType.PROPOSAL: "Proposal created",
}


class OutreachDraftNotFoundError(Exception):
    pass


class PdfNotSupportedError(Exception):
    """Raised when PDF export is requested for a draft type other than
    proposal — email/WhatsApp are sent through their own channels, not
    exported as documents."""

    pass


async def create_draft(
    session: AsyncSession, lead_id: uuid.UUID, *, type: str, subject: str | None, content: str
) -> OutreachDraftResponse:
    try:
        lead = await lead_repository.get_by_id(session, lead_id)
    except Exception as exc:
        logger.error("Failed to fetch lead %s", lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if lead is None:
        raise LeadNotFoundError(f"Lead {lead_id} not found")

    try:
        draft = await outreach_draft_repository.create_draft(
            session, lead_id, type=type, subject=subject, content=content
        )
        await activity_repository.add_activity(
            session, lead_id, type=type, description=_ACTIVITY_DESCRIPTIONS.get(type, f"{type} draft saved")
        )
    except Exception as exc:
        logger.error("Failed to save %s draft for lead %s", type, lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    return OutreachDraftResponse.model_validate(draft)


async def get_latest_draft(session: AsyncSession, lead_id: uuid.UUID, *, type: str) -> OutreachDraftResponse:
    try:
        draft = await outreach_draft_repository.get_latest_by_lead_and_type(session, lead_id, type=type)
    except Exception as exc:
        logger.error("Failed to fetch latest %s draft for lead %s", type, lead_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if draft is None:
        raise OutreachDraftNotFoundError(f"No {type} draft found for lead {lead_id}")
    return OutreachDraftResponse.model_validate(draft)


async def update_draft(
    session: AsyncSession, draft_id: uuid.UUID, *, subject: str | None, content: str
) -> OutreachDraftResponse:
    try:
        draft = await outreach_draft_repository.update_draft(session, draft_id, subject=subject, content=content)
    except Exception as exc:
        logger.error("Failed to update draft %s", draft_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if draft is None:
        raise OutreachDraftNotFoundError(f"Draft {draft_id} not found")
    return OutreachDraftResponse.model_validate(draft)


async def generate_draft_pdf(session: AsyncSession, draft_id: uuid.UUID) -> bytes:
    try:
        draft = await outreach_draft_repository.get_by_id(session, draft_id)
    except Exception as exc:
        logger.error("Failed to fetch draft %s", draft_id, exc_info=exc)
        raise LeadServiceUnavailableError("Database connection failed") from exc

    if draft is None:
        raise OutreachDraftNotFoundError(f"Draft {draft_id} not found")
    if draft.type != OutreachType.PROPOSAL:
        raise PdfNotSupportedError(f"PDF export is only supported for proposal drafts, not {draft.type}")

    return render_proposal_pdf(draft.content)
