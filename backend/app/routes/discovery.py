from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.discovery import DiscoveryRequest, DiscoveryResponse, JobStatusResponse
from app.services import discovery_service
from app.services.discovery_service import DiscoveryQueueError, JobNotFoundError

router = APIRouter(tags=["discovery"])


def get_redis_pool(request: Request) -> ArqRedis:
    redis = request.app.state.arq_redis
    if redis is None:
        raise HTTPException(status_code=503, detail="Queue backend (Redis) is unavailable")
    return redis


@router.post("/start-discovery", response_model=DiscoveryResponse, status_code=202)
async def start_discovery(
    payload: DiscoveryRequest,
    redis: ArqRedis = Depends(get_redis_pool),
) -> DiscoveryResponse:
    try:
        return await discovery_service.start_discovery(redis, payload)
    except DiscoveryQueueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/discovery-jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    redis: ArqRedis = Depends(get_redis_pool),
) -> JobStatusResponse:
    try:
        return await discovery_service.get_job_status(redis, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
