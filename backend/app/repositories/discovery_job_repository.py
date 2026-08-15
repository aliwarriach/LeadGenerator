import uuid

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.discovery_job import DiscoveryJob, DiscoveryJobEvent, DiscoveryRun
from app.schemas.errors import ErrorDetail


async def insert_run(
    session: AsyncSession,
    *,
    country: str,
    city: str,
    custom_niche: str,
    min_rating: float | None,
    total_jobs: int,
) -> DiscoveryRun:
    run = DiscoveryRun(
        country=country, city=city, custom_niche=custom_niche, min_rating=min_rating, total_jobs=total_jobs
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return run


async def insert_job(
    session: AsyncSession, *, run_id: uuid.UUID, source: str, query: str, location: str
) -> DiscoveryJob:
    job = DiscoveryJob(run_id=run_id, source=source, query=query, location=location)
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def set_arq_job_id(session: AsyncSession, job_id: uuid.UUID, arq_job_id: str) -> None:
    await session.execute(update(DiscoveryJob).where(DiscoveryJob.id == job_id).values(arq_job_id=arq_job_id))
    await session.commit()


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> DiscoveryRun | None:
    result = await session.execute(select(DiscoveryRun).where(DiscoveryRun.id == run_id))
    return result.scalar_one_or_none()


async def list_runs(session: AsyncSession, *, limit: int, offset: int) -> tuple[list[DiscoveryRun], int]:
    total = (await session.execute(select(func.count()).select_from(DiscoveryRun))).scalar_one()
    result = await session.execute(
        select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all()), total


async def list_jobs_for_run(session: AsyncSession, run_id: uuid.UUID) -> list[DiscoveryJob]:
    result = await session.execute(
        select(DiscoveryJob).where(DiscoveryJob.run_id == run_id).order_by(DiscoveryJob.created_at.asc())
    )
    return list(result.scalars().all())


async def list_jobs_for_recent_runs(session: AsyncSession, *, run_limit: int) -> list[DiscoveryJob]:
    """All jobs belonging to the most recent `run_limit` runs, in one query —
    bounds the run-stats aggregation to a fixed cost instead of scanning full
    history as the table grows."""
    recent_run_ids = select(DiscoveryRun.id).order_by(DiscoveryRun.created_at.desc()).limit(run_limit)
    result = await session.execute(select(DiscoveryJob).where(DiscoveryJob.run_id.in_(recent_run_ids)))
    return list(result.scalars().all())


async def get_job(session: AsyncSession, job_id: uuid.UUID) -> DiscoveryJob | None:
    result = await session.execute(select(DiscoveryJob).where(DiscoveryJob.id == job_id))
    return result.scalar_one_or_none()


def _apply_job_filters(
    stmt: Select, *, status: str | None, source: str | None, run_id: uuid.UUID | None
) -> Select:
    if status is not None:
        stmt = stmt.where(DiscoveryJob.status == status)
    if source is not None:
        stmt = stmt.where(DiscoveryJob.source == source)
    if run_id is not None:
        stmt = stmt.where(DiscoveryJob.run_id == run_id)
    return stmt


async def list_jobs(
    session: AsyncSession,
    *,
    status: str | None = None,
    source: str | None = None,
    run_id: uuid.UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DiscoveryJob], int]:
    """Queue-wide job listing (across runs), filterable — powers the "list of
    jobs in queue, running, and completed" view."""
    filter_kwargs = dict(status=status, source=source, run_id=run_id)

    count_stmt = _apply_job_filters(select(func.count()).select_from(DiscoveryJob), **filter_kwargs)
    total = (await session.execute(count_stmt)).scalar_one()

    items_stmt = _apply_job_filters(select(DiscoveryJob), **filter_kwargs)
    items_stmt = items_stmt.order_by(DiscoveryJob.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(items_stmt)
    return list(result.scalars().all()), total


async def update_job_status(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    status: str,
    error: ErrorDetail | None = None,
    started_at=None,
    finished_at=None,
) -> None:
    values: dict = {"status": status}
    if error is not None:
        values["error_code"] = error.code
        values["error_message"] = error.message
        values["error_retryable"] = error.retryable
        values["error_retry_after_seconds"] = error.retry_after_seconds
    if started_at is not None:
        values["started_at"] = started_at
    if finished_at is not None:
        values["finished_at"] = finished_at

    await session.execute(update(DiscoveryJob).where(DiscoveryJob.id == job_id).values(**values))
    await session.commit()


async def update_job_progress(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    current_business_name: str | None = None,
    leads_found_delta: int = 0,
    leads_saved_delta: int = 0,
    extraction_failure_delta: int = 0,
) -> None:
    values: dict = {}
    if current_business_name is not None:
        values["current_business_name"] = current_business_name
    if leads_found_delta:
        values["leads_found_session"] = DiscoveryJob.leads_found_session + leads_found_delta
    if leads_saved_delta:
        values["leads_saved_session"] = DiscoveryJob.leads_saved_session + leads_saved_delta
    if extraction_failure_delta:
        values["extraction_failures_session"] = (
            DiscoveryJob.extraction_failures_session + extraction_failure_delta
        )
    if not values:
        return

    await session.execute(update(DiscoveryJob).where(DiscoveryJob.id == job_id).values(**values))
    await session.commit()


async def set_stop_requested(session: AsyncSession, job_id: uuid.UUID) -> DiscoveryJob | None:
    result = await session.execute(
        update(DiscoveryJob)
        .where(DiscoveryJob.id == job_id)
        .values(stop_requested=True)
        .returning(DiscoveryJob)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def is_stop_requested(session: AsyncSession, job_id: uuid.UUID) -> bool:
    result = await session.execute(select(DiscoveryJob.stop_requested).where(DiscoveryJob.id == job_id))
    return bool(result.scalar_one_or_none())


async def insert_event(
    session: AsyncSession,
    job_id: uuid.UUID,
    *,
    event_type: str,
    message: str,
    code: str | None = None,
    payload: dict | None = None,
) -> DiscoveryJobEvent:
    event = DiscoveryJobEvent(job_id=job_id, event_type=event_type, code=code, message=message, payload=payload)
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def list_events(
    session: AsyncSession, job_id: uuid.UUID, *, after: int | None = None, limit: int = 100
) -> list[DiscoveryJobEvent]:
    stmt = select(DiscoveryJobEvent).where(DiscoveryJobEvent.job_id == job_id)
    if after is not None:
        stmt = stmt.where(DiscoveryJobEvent.id > after)
    stmt = stmt.order_by(DiscoveryJobEvent.id.asc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())
