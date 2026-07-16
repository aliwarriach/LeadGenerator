import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.activity import ActivityCreateRequest, ActivityListResponse, ActivityResponse
from app.services import activity_service
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("/{lead_id}", response_model=ActivityResponse)
async def create_activity(
    lead_id: uuid.UUID,
    request: ActivityCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ActivityResponse:
    try:
        return await activity_service.create_activity(
            session, lead_id, type=request.type, description=request.description
        )
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/{lead_id}", response_model=ActivityListResponse)
async def list_activities(
    lead_id: uuid.UUID, session: AsyncSession = Depends(get_db_session)
) -> ActivityListResponse:
    try:
        return await activity_service.list_activities(session, lead_id)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LeadServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
