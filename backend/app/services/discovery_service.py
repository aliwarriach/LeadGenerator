import logging

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus

from app.schemas.discovery import DiscoveryJobRef, DiscoveryRequest, DiscoveryResponse, JobStatusResponse

logger = logging.getLogger(__name__)


class DiscoveryQueueError(Exception):
    pass


class JobNotFoundError(Exception):
    pass


def _build_location(city: str, country: str) -> str:
    return f"{city}, {country}"


async def start_discovery(redis: ArqRedis, request: DiscoveryRequest) -> DiscoveryResponse:
    """Queue all discovery sources, in parallel, for every requested city.

    A multi-city request (e.g. city="Lahore, Karachi") fans out into a full
    set of source jobs per city — each city is an independent search, not a
    single combined query, since Maps/Facebook/Serper searches are inherently
    per-location.
    """
    jobs: list[DiscoveryJobRef] = []

    for city in request.cities:
        location = _build_location(city, request.country)
        for source, job_name in (
            ("google_maps", "scrape_google_maps_job"),
            ("facebook", "scrape_facebook_job"),
            ("serper", "scrape_serper_job"),
        ):
            job = await redis.enqueue_job(
                job_name, request.custom_niche, location, request.min_rating
            )
            if job is None:
                logger.error(
                    "Failed to enqueue %s job for niche=%r city=%r", job_name, request.custom_niche, city
                )
                raise DiscoveryQueueError(f"Could not queue {source} discovery job for {city}")
            jobs.append(DiscoveryJobRef(source=source, city=city, job_id=job.job_id))

    return DiscoveryResponse(
        country=request.country,
        city=request.city,
        custom_niche=request.custom_niche,
        min_rating=request.min_rating,
        jobs=jobs,
    )


async def get_job_status(redis: ArqRedis, job_id: str) -> JobStatusResponse:
    """Poll an ARQ job's current state for frontend progress tracking.

    Before completion, only `Job.info()` (enqueue-time metadata) is
    available. Once the job has been attempted, `Job.result_info()` also
    carries timing and the outcome — a dict result on success, or the
    stringified exception under `error` on failure (job functions here
    return plain dicts, never raise past their own retry handling, so a
    populated `error` means something outside normal retries broke).
    """
    job = Job(job_id, redis)
    status = await job.status()
    if status == JobStatus.not_found:
        raise JobNotFoundError(f"Job {job_id} not found")

    result_info = await job.result_info()
    if result_info is not None:
        result = None
        error = None
        if result_info.success:
            result = result_info.result if isinstance(result_info.result, dict) else {"value": result_info.result}
        else:
            error = str(result_info.result)

        return JobStatusResponse(
            job_id=job_id,
            status=status.value,
            function=result_info.function,
            enqueue_time=result_info.enqueue_time,
            start_time=result_info.start_time,
            finish_time=result_info.finish_time,
            success=result_info.success,
            result=result,
            error=error,
        )

    job_def = await job.info()
    return JobStatusResponse(
        job_id=job_id,
        status=status.value,
        function=job_def.function if job_def else None,
        enqueue_time=job_def.enqueue_time if job_def else None,
    )
