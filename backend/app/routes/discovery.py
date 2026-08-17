import uuid
from typing import Literal

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.schemas.discovery import DiscoveryRequest, DiscoveryResponse
from app.schemas.discovery_job import (
    DiscoveryJobEventListResponse,
    DiscoveryJobListResponse,
    DiscoveryJobResponse,
    DiscoveryJobStatusLiteral,
    DiscoveryRunListResponse,
    DiscoveryRunResponse,
    DiscoveryRunStatsResponse,
    DiscoverySourceLiteral,
)
from app.schemas.errors import ApiError, ErrorDetail
from app.services import discovery_service, job_tracking_service
from app.services.discovery_service import DiscoveryQueueError
from app.services.job_tracking_service import DiscoveryJobNotFoundError, DiscoveryRunNotFoundError

router = APIRouter(tags=["discovery"])


def get_redis_pool(request: Request) -> ArqRedis | None:
    """The ARQ pool, or None when this process doesn't own the queue.

    In "db" dispatch mode the API never enqueues — it writes the DiscoveryJob
    row and app/workers/dispatcher.py picks it up — so having no Redis is the
    expected state there, not a 503-worthy outage.
    """
    if get_settings().dispatch_mode == "db":
        return None

    redis = request.app.state.arq_redis
    if redis is None:
        raise ApiError(
            503,
            ErrorDetail(code="queue_unavailable", message="Queue backend (Redis) is unavailable", retryable=True),
        )
    return redis


@router.post("/start-discovery", response_model=DiscoveryResponse, status_code=202)
async def start_discovery(
    payload: DiscoveryRequest,
    redis: ArqRedis | None = Depends(get_redis_pool),
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryResponse:
    try:
        return await discovery_service.start_discovery(redis, session, payload)
    except DiscoveryQueueError as exc:
        raise ApiError(503, ErrorDetail(code="queue_unavailable", message=str(exc), retryable=True)) from exc


@router.get("/discovery-runs", response_model=DiscoveryRunListResponse)
async def list_runs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryRunListResponse:
    return await job_tracking_service.list_runs(session, page=page, page_size=page_size)


@router.get("/discovery-runs/stats", response_model=DiscoveryRunStatsResponse)
async def get_run_stats(session: AsyncSession = Depends(get_db_session)) -> DiscoveryRunStatsResponse:
    return await job_tracking_service.get_run_stats(session)


@router.get("/discovery-runs/{run_id}", response_model=DiscoveryRunResponse)
async def get_run_detail(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryRunResponse:
    try:
        return await job_tracking_service.get_run_detail(session, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise ApiError(404, ErrorDetail(code="run_not_found", message=str(exc), retryable=False)) from exc


@router.post("/discovery-runs/{run_id}/stop", response_model=DiscoveryRunResponse)
async def stop_run(
    run_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryRunResponse:
    try:
        return await job_tracking_service.request_stop_for_run(session, run_id)
    except DiscoveryRunNotFoundError as exc:
        raise ApiError(404, ErrorDetail(code="run_not_found", message=str(exc), retryable=False)) from exc


@router.get("/discovery-jobs", response_model=DiscoveryJobListResponse)
async def list_jobs(
    status: DiscoveryJobStatusLiteral | None = None,
    source: DiscoverySourceLiteral | None = None,
    run_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryJobListResponse:
    return await job_tracking_service.list_jobs(
        session, status=status, source=source, run_id=run_id, page=page, page_size=page_size
    )


@router.get("/discovery-jobs/{job_id}", response_model=DiscoveryJobResponse)
async def get_job_status(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryJobResponse:
    try:
        return await job_tracking_service.get_job_detail(session, job_id)
    except DiscoveryJobNotFoundError as exc:
        raise ApiError(404, ErrorDetail(code="job_not_found", message=str(exc), retryable=False)) from exc


@router.post("/discovery-jobs/{job_id}/stop", response_model=DiscoveryJobResponse)
async def stop_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryJobResponse:
    try:
        return await job_tracking_service.request_stop(session, job_id)
    except DiscoveryJobNotFoundError as exc:
        raise ApiError(404, ErrorDetail(code="job_not_found", message=str(exc), retryable=False)) from exc


@router.get("/discovery-jobs/{job_id}/events", response_model=DiscoveryJobEventListResponse)
async def list_job_events(
    job_id: uuid.UUID,
    after: int | None = Query(default=None, ge=0, description="Cursor from a previous response's next_cursor"),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> DiscoveryJobEventListResponse:
    try:
        return await job_tracking_service.list_job_events(session, job_id, after=after, limit=limit)
    except DiscoveryJobNotFoundError as exc:
        raise ApiError(404, ErrorDetail(code="job_not_found", message=str(exc), retryable=False)) from exc
