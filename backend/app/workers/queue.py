from arq.connections import ArqRedis, RedisSettings, create_pool

from app.core.config import get_settings
from app.workers.discovery_worker import (
    scrape_facebook_job,
    scrape_google_maps_job,
    scrape_serper_job,
)

# Per-job timeout and retry ceiling. Scraping itself is slow (dozens of
# listings, human-like delays), but the dominant cost is PageSpeed
# enrichment — leads are enriched sequentially, and a real Lighthouse audit
# against a live site commonly takes 40-60s+ per lead (confirmed live). A
# job scraping 50 leads-with-websites can legitimately run 30-45+ minutes;
# this must stay well above that rather than killing jobs mid-enrichment.
JOB_TIMEOUT_SECONDS = 3600
JOB_MAX_TRIES = 3


def get_redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


async def get_arq_pool() -> ArqRedis:
    return await create_pool(get_redis_settings())


class WorkerSettings:
    """Entry point for the ARQ worker process: `arq app.workers.queue.WorkerSettings`."""

    functions = [scrape_google_maps_job, scrape_facebook_job, scrape_serper_job]
    redis_settings = get_redis_settings()
    job_timeout = JOB_TIMEOUT_SECONDS
    max_tries = JOB_MAX_TRIES
    # Browser automation is CPU/memory heavy — cap concurrent jobs per worker
    # process rather than defaulting to arq's higher default concurrency.
    max_jobs = 4
