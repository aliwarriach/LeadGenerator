"""Bridges the API's database-backed job queue to a local ARQ queue.

Runs on the machine that owns the scrapers, alongside the ARQ worker. When the
API is deployed somewhere that cannot reach this machine's Redis (Settings.
dispatch_mode == "db"), it only writes DiscoveryJob rows; this process claims
those rows and enqueues them into the Redis the worker actually consumes.

Its own process rather than an ARQ cron job: cron jobs are subject to the
worker's `max_jobs` budget, so a full slate of scrapes — which legitimately run
30-45 minutes each — would starve dispatching for that entire time.
"""

import asyncio
import logging

from arq.connections import ArqRedis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.models.discovery_job import DiscoveryJob
from app.repositories import discovery_job_repository
from app.schemas.errors import ErrorDetail
from app.services import job_tracking_service
from app.services.discovery_service import JOB_NAMES_BY_SOURCE
from app.workers.queue import get_arq_pool

logger = logging.getLogger(__name__)


async def _dispatch_job(
    session: AsyncSession, redis: ArqRedis, job: DiscoveryJob, min_rating: float | None
) -> bool:
    """Enqueue one claimed job and record the ARQ id. True if it was dispatched."""
    job_name = JOB_NAMES_BY_SOURCE.get(job.source)
    if job_name is None:
        # No worker function for this source in this build. Retrying can never
        # succeed, so the row is failed rather than re-claimed on every poll
        # forever.
        logger.error("Discovery job %s has unknown source %r — failing it", job.id, job.source)
        await job_tracking_service.mark_job_enqueue_failed(
            session,
            job.id,
            ErrorDetail(
                code="validation_error",
                message=f"Unknown discovery source {job.source!r}",
                retryable=False,
            ),
        )
        return False

    arq_job = await redis.enqueue_job(
        job_name, str(job.id), job.query, job.location, min_rating, _job_id=str(job.id)
    )

    # Using the DiscoveryJob id as the ARQ job id makes dispatching idempotent:
    # ARQ refuses to enqueue an id it already holds and returns None, which is
    # exactly the state left behind if this process died between enqueueing and
    # recording arq_job_id. Recording it now is the recovery — re-enqueueing
    # would run the same scrape twice. Genuine Redis failures raise instead of
    # returning None, so they can't be mistaken for this case.
    if arq_job is None:
        logger.info("Discovery job %s was already queued — recording its id", job.id)

    await discovery_job_repository.set_arq_job_id(session, job.id, str(job.id))
    return True


async def dispatch_pending_jobs(redis: ArqRedis, *, batch_size: int) -> int:
    """Claim one batch of undispatched jobs and enqueue them.

    Returns how many were dispatched. Each job commits on its own (via the
    repository helpers); that releases the remaining row locks early, which is
    harmless because `_dispatch_job` is idempotent per job id.
    """
    dispatched = 0
    async with async_session_factory() as session:
        claimed = await discovery_job_repository.claim_pending_jobs(session, limit=batch_size)
        for job, min_rating in claimed:
            if await _dispatch_job(session, redis, job, min_rating):
                dispatched += 1
    return dispatched


async def run_dispatcher(settings: Settings | None = None) -> None:
    """Poll for pending jobs until cancelled."""
    settings = settings or get_settings()
    redis = await get_arq_pool()
    logger.info(
        "Dispatcher started — polling every %.1fs, up to %d job(s) per cycle",
        settings.dispatcher_poll_seconds,
        settings.dispatcher_batch_size,
    )

    try:
        while True:
            try:
                dispatched = await dispatch_pending_jobs(
                    redis, batch_size=settings.dispatcher_batch_size
                )
                if dispatched:
                    logger.info("Dispatched %d pending discovery job(s)", dispatched)
            except (RedisError, SQLAlchemyError, OSError) as exc:
                # An outage on either side is transient and must not kill the
                # loop: the rows stay pending (arq_job_id still NULL) and the
                # next poll picks them up. Deliberately not marking them failed
                # — a dropped connection is not a bad job.
                logger.error("Dispatch cycle failed, retrying on the next poll: %s", exc)

            await asyncio.sleep(settings.dispatcher_poll_seconds)
    finally:
        await redis.close()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        asyncio.run(run_dispatcher())
    except KeyboardInterrupt:
        logger.info("Dispatcher stopped")


if __name__ == "__main__":
    main()
