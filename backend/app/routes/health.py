from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.health import HealthStatus
from app.services import health_service
from app.services.health_service import DatabaseUnavailableError

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def get_health(session: AsyncSession = Depends(get_db_session)) -> HealthStatus:
    try:
        return await health_service.check_health(session)
    except DatabaseUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
