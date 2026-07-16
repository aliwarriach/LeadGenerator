import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.outreach_draft import (
    OutreachDraftCreateRequest,
    OutreachDraftResponse,
    OutreachDraftTypeLiteral,
    OutreachDraftUpdateRequest,
)
from app.services import outreach_draft_service
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError
from app.services.outreach_draft_service import OutreachDraftNotFoundError, PdfNotSupportedError
from app.services.pdf_service import PdfGenerationError

router = APIRouter(prefix="/outreach-drafts", tags=["outreach-drafts"])


@router.post("/{lead_id}", response_model=OutreachDraftResponse)
async def create_draft(
    lead_id: uuid.UUID,
    request: OutreachDraftCreateRequest,
    type: OutreachDraftTypeLiteral = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> OutreachDraftResponse:
    """Saves a generated outreach draft (email, WhatsApp, or proposal) and
    logs a matching activity."""
    try:
        return await outreach_draft_service.create_draft(
            session, lead_id, type=type, subject=request.subject, content=request.content
        )
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{lead_id}", response_model=OutreachDraftResponse)
async def get_latest_draft(
    lead_id: uuid.UUID,
    type: OutreachDraftTypeLiteral = Query(...),
    session: AsyncSession = Depends(get_db_session),
) -> OutreachDraftResponse:
    try:
        return await outreach_draft_service.get_latest_draft(session, lead_id, type=type)
    except OutreachDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.patch("/{draft_id}", response_model=OutreachDraftResponse)
async def update_draft(
    draft_id: uuid.UUID,
    request: OutreachDraftUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> OutreachDraftResponse:
    try:
        return await outreach_draft_service.update_draft(
            session, draft_id, subject=request.subject, content=request.content
        )
    except OutreachDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/{draft_id}/pdf")
async def generate_draft_pdf(draft_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)) -> Response:
    """PDF export — proposal drafts only. Email/WhatsApp are sent through
    their own channels, not exported as documents."""
    try:
        pdf_bytes = await outreach_draft_service.generate_draft_pdf(session, draft_id)
    except OutreachDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PdfNotSupportedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PdfGenerationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="proposal-{draft_id}.pdf"'},
    )
