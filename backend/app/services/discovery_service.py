import logging

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.discovery import DiscoveryJobRef, DiscoveryRequest, DiscoveryResponse
from app.schemas.errors import ErrorDetail
from app.services import job_tracking_service

logger = logging.getLogger(__name__)

_JOB_NAMES: tuple[tuple[str, str], ...] = (
    ("google_maps", "scrape_google_maps_job"),
    ("facebook", "scrape_facebook_job"),
    ("serper", "scrape_serper_job"),
)


class DiscoveryQueueError(Exception):
    pass


def _build_location(city: str, country: str) -> str:
    return f"{city}, {country}"


async def start_discovery(
    redis: ArqRedis, session: AsyncSession, request: DiscoveryRequest
) -> DiscoveryResponse:
    """Queue all discovery sources, in parallel, for every requested city.

    A multi-city request (e.g. city="Lahore, Karachi") fans out into a full
    set of source jobs per city — each city is an independent search, not a
    single combined query, since Maps/Facebook/Serper searches are inherently
    per-location.

    Each fan-out job gets its own DiscoveryJob row *before* being enqueued —
    the row's id (not ARQ's job id) is what's returned to the caller and is
    what the worker reports progress against, so the tracking row always
    exists before the ARQ worker (a separate process) could possibly start it.
    """
    run = await job_tracking_service.create_run(
        session,
        country=request.country,
        city=request.city,
        custom_niche=request.custom_niche,
        min_rating=request.min_rating,
        total_jobs=len(request.cities) * len(_JOB_NAMES),
    )

    jobs: list[DiscoveryJobRef] = []

    for city in request.cities:
        location = _build_location(city, request.country)
        for source, job_name in _JOB_NAMES:
            job_row = await job_tracking_service.create_job(
                session, run_id=run.id, source=source, query=request.custom_niche, location=location
            )

            arq_job = await redis.enqueue_job(
                job_name, str(job_row.id), request.custom_niche, location, request.min_rating
            )
            if arq_job is None:
                logger.error(
                    "Failed to enqueue %s job for niche=%r city=%r", job_name, request.custom_niche, city
                )
                await job_tracking_service.mark_job_enqueue_failed(
                    session,
                    job_row.id,
                    ErrorDetail(
                        code="queue_unavailable",
                        message=f"Could not queue {source} discovery job for {city}",
                        retryable=True,
                    ),
                )
                raise DiscoveryQueueError(f"Could not queue {source} discovery job for {city}")

            await job_tracking_service.attach_arq_job_id(session, job_row.id, arq_job.job_id)
            jobs.append(DiscoveryJobRef(source=source, city=city, job_id=job_row.id))

    return DiscoveryResponse(
        run_id=run.id,
        country=request.country,
        city=request.city,
        custom_niche=request.custom_niche,
        min_rating=request.min_rating,
        jobs=jobs,
    )
