import logging
import math
import uuid
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.discovery_job import TERMINAL_JOB_STATUSES, DiscoveryEventType, DiscoveryJob, DiscoveryJobStatus
from app.repositories import discovery_job_repository, lead_repository
from app.schemas.discovery_job import (
    DiscoveryJobEventListResponse,
    DiscoveryJobEventResponse,
    DiscoveryJobListResponse,
    DiscoveryJobResponse,
    DiscoveryRunListResponse,
    DiscoveryRunResponse,
    DiscoveryRunStatsResponse,
    DiscoveryRunSummary,
    DiscoveryRunWarning,
    SourcePerformance,
)
from app.schemas.errors import ErrorDetail

logger = logging.getLogger(__name__)

# Below this many total attempts, a failure-rate warning is more noise than
# signal (e.g. 1 failure out of 1 attempt is not "high failure rate").
_MIN_ATTEMPTS_FOR_FAILURE_WARNING = 5
_HIGH_FAILURE_RATE_THRESHOLD = 0.4

# How many of the most recent runs the "run estimate" stats card (frontend
# Discovery screen) aggregates over — bounds the query cost as run history
# grows; recent runs are also the most representative of current conditions.
_RECENT_RUNS_LIMIT_FOR_STATS = 200

_TERMINAL_SEVERITY = {
    DiscoveryJobStatus.FAILED: 5,
    DiscoveryJobStatus.BLOCKED: 4,
    DiscoveryJobStatus.STOPPED: 3,
    DiscoveryJobStatus.SKIPPED_COOLDOWN: 2,
    DiscoveryJobStatus.COMPLETED: 1,
}


class DiscoveryRunNotFoundError(Exception):
    pass


class DiscoveryJobNotFoundError(Exception):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _min_or_none(values: Iterable[datetime | None]) -> datetime | None:
    present = [v for v in values if v is not None]
    return min(present) if present else None


def _max_or_none(values: Iterable[datetime | None]) -> datetime | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


# ---- pure functions (no DB — trivially unit-testable) ----------------------


def derive_run_status(jobs: list[DiscoveryJob]) -> str:
    """A run has no status column of its own (see models/discovery_job.py) —
    its status is always derived from its child jobs."""
    if not jobs:
        return DiscoveryJobStatus.PENDING

    statuses = [DiscoveryJobStatus(job.status) for job in jobs]
    if any(status == DiscoveryJobStatus.RUNNING for status in statuses):
        return DiscoveryJobStatus.RUNNING
    if any(status == DiscoveryJobStatus.PENDING for status in statuses):
        return DiscoveryJobStatus.PENDING

    # All terminal — surface the single most severe outcome among children
    # (a failed/blocked source outweighs a completed one in the run summary).
    return max(statuses, key=lambda status: _TERMINAL_SEVERITY.get(status, 0))


def compute_warnings(jobs: list[DiscoveryJob]) -> list[DiscoveryRunWarning]:
    warnings: list[DiscoveryRunWarning] = []
    for job in jobs:
        attempted = job.leads_found_session + job.extraction_failures_session
        if attempted < _MIN_ATTEMPTS_FOR_FAILURE_WARNING:
            continue
        failure_rate = job.extraction_failures_session / attempted
        if failure_rate > _HIGH_FAILURE_RATE_THRESHOLD:
            warnings.append(
                DiscoveryRunWarning(
                    code="high_failure_rate",
                    source=job.source,
                    message=(
                        f"High failure rate on {job.source} scraper "
                        f"({round(failure_rate * 100)}% of {attempted} attempts failed)"
                    ),
                )
            )
    return warnings


def _run_finished_at(jobs: list[DiscoveryJob], status: str) -> datetime | None:
    if status in (DiscoveryJobStatus.RUNNING, DiscoveryJobStatus.PENDING):
        return None
    if not all(job.finished_at is not None for job in jobs):
        return None
    return _max_or_none(job.finished_at for job in jobs)


# ---- session-based functions (route / discovery_service call sites) --------


async def create_run(
    session: AsyncSession, *, country: str, city: str, custom_niche: str, min_rating: float | None, total_jobs: int
):
    return await discovery_job_repository.insert_run(
        session, country=country, city=city, custom_niche=custom_niche, min_rating=min_rating, total_jobs=total_jobs
    )


async def create_job(session: AsyncSession, *, run_id: uuid.UUID, source: str, query: str, location: str):
    return await discovery_job_repository.insert_job(session, run_id=run_id, source=source, query=query, location=location)


async def attach_arq_job_id(session: AsyncSession, job_id: uuid.UUID, arq_job_id: str) -> None:
    await discovery_job_repository.set_arq_job_id(session, job_id, arq_job_id)


async def mark_job_enqueue_failed(session: AsyncSession, job_id: uuid.UUID, error: ErrorDetail) -> None:
    await discovery_job_repository.update_job_status(
        session, job_id, status=DiscoveryJobStatus.FAILED, error=error, finished_at=_utcnow()
    )


async def get_run_detail(session: AsyncSession, run_id: uuid.UUID) -> DiscoveryRunResponse:
    run = await discovery_job_repository.get_run(session, run_id)
    if run is None:
        raise DiscoveryRunNotFoundError(f"Run {run_id} not found")

    jobs = await discovery_job_repository.list_jobs_for_run(session, run_id)
    status = derive_run_status(jobs)

    return DiscoveryRunResponse(
        id=run.id,
        country=run.country,
        city=run.city,
        custom_niche=run.custom_niche,
        min_rating=run.min_rating,
        created_at=run.created_at,
        status=status,
        started_at=_min_or_none(job.started_at for job in jobs),
        finished_at=_run_finished_at(jobs, status),
        warnings=compute_warnings(jobs),
        jobs=[DiscoveryJobResponse.model_validate(job) for job in jobs],
    )


async def list_runs(session: AsyncSession, *, page: int, page_size: int) -> DiscoveryRunListResponse:
    offset = (page - 1) * page_size
    runs, total = await discovery_job_repository.list_runs(session, limit=page_size, offset=offset)

    summaries = []
    for run in runs:
        # One jobs-lookup per run — acceptable here since this endpoint isn't
        # the tight-polling one (that's GET .../events); the run-detail and
        # events endpoints carry the live-polling load instead.
        jobs = await discovery_job_repository.list_jobs_for_run(session, run.id)
        summaries.append(
            DiscoveryRunSummary(
                id=run.id,
                country=run.country,
                city=run.city,
                custom_niche=run.custom_niche,
                min_rating=run.min_rating,
                created_at=run.created_at,
                status=derive_run_status(jobs),
            )
        )

    total_pages = math.ceil(total / page_size) if total else 0
    return DiscoveryRunListResponse(items=summaries, total=total, page=page, page_size=page_size, total_pages=total_pages)


_NON_TERMINAL_RUN_STATUSES = frozenset({DiscoveryJobStatus.PENDING, DiscoveryJobStatus.RUNNING})


async def get_run_stats(session: AsyncSession) -> DiscoveryRunStatsResponse:
    """Duration/leads/source figures average over fully-completed runs only,
    among the most recent _RECENT_RUNS_LIMIT_FOR_STATS — stopped/failed/
    blocked runs would skew a "typical run" figure. success_rate is measured
    across all terminal runs instead, since it exists specifically to surface
    those excluded outcomes."""
    jobs = await discovery_job_repository.list_jobs_for_recent_runs(session, run_limit=_RECENT_RUNS_LIMIT_FOR_STATS)

    jobs_by_run: dict[uuid.UUID, list[DiscoveryJob]] = defaultdict(list)
    for job in jobs:
        jobs_by_run[job.run_id].append(job)

    durations_seconds: list[float] = []
    leads_saved_per_run: list[int] = []
    leads_saved_by_source: dict[str, list[int]] = defaultdict(list)
    terminal_run_count = 0

    for run_jobs in jobs_by_run.values():
        status = derive_run_status(run_jobs)
        if status in _NON_TERMINAL_RUN_STATUSES:
            continue
        terminal_run_count += 1
        if status != DiscoveryJobStatus.COMPLETED:
            continue

        leads_saved_per_run.append(sum(job.leads_saved_session for job in run_jobs))
        for job in run_jobs:
            leads_saved_by_source[job.source].append(job.leads_saved_session)

        started_at = _min_or_none(job.started_at for job in run_jobs)
        finished_at = _max_or_none(job.finished_at for job in run_jobs)
        if started_at is not None and finished_at is not None:
            durations_seconds.append((finished_at - started_at).total_seconds())

    completed_run_count = len(leads_saved_per_run)
    leads_by_source = sorted(
        (
            SourcePerformance(source=source, avg_leads_saved=sum(values) / len(values))
            for source, values in leads_saved_by_source.items()
        ),
        key=lambda item: item.avg_leads_saved,
        reverse=True,
    )

    return DiscoveryRunStatsResponse(
        completed_run_count=completed_run_count,
        avg_duration_seconds=(sum(durations_seconds) / len(durations_seconds)) if durations_seconds else None,
        avg_leads_saved=(sum(leads_saved_per_run) / len(leads_saved_per_run)) if leads_saved_per_run else None,
        total_leads_saved=sum(leads_saved_per_run),
        success_rate=(completed_run_count / terminal_run_count) if terminal_run_count else None,
        leads_by_source=leads_by_source,
    )


async def get_job_detail(session: AsyncSession, job_id: uuid.UUID) -> DiscoveryJobResponse:
    job = await discovery_job_repository.get_job(session, job_id)
    if job is None:
        raise DiscoveryJobNotFoundError(f"Job {job_id} not found")

    counts = await lead_repository.count_by_source(session, [job.source])
    response = DiscoveryJobResponse.model_validate(job)
    response.total_leads_scraped_by_source = counts.get(job.source, 0)
    return response


async def list_jobs(
    session: AsyncSession,
    *,
    status: str | None,
    source: str | None,
    run_id: uuid.UUID | None,
    page: int,
    page_size: int,
) -> DiscoveryJobListResponse:
    offset = (page - 1) * page_size
    jobs, total = await discovery_job_repository.list_jobs(
        session, status=status, source=source, run_id=run_id, limit=page_size, offset=offset
    )
    total_pages = math.ceil(total / page_size) if total else 0
    return DiscoveryJobListResponse(
        items=[DiscoveryJobResponse.model_validate(job) for job in jobs],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


async def list_job_events(
    session: AsyncSession, job_id: uuid.UUID, *, after: int | None, limit: int
) -> DiscoveryJobEventListResponse:
    job = await discovery_job_repository.get_job(session, job_id)
    if job is None:
        raise DiscoveryJobNotFoundError(f"Job {job_id} not found")

    events = await discovery_job_repository.list_events(session, job_id, after=after, limit=limit)
    # Not a has-more flag — always the cursor to pass as `after` on the next
    # poll. Falls back to the caller's own cursor when nothing new landed.
    next_cursor = events[-1].id if events else after
    return DiscoveryJobEventListResponse(
        items=[DiscoveryJobEventResponse.model_validate(event) for event in events], next_cursor=next_cursor
    )


async def request_stop(session: AsyncSession, job_id: uuid.UUID) -> DiscoveryJobResponse:
    job = await discovery_job_repository.set_stop_requested(session, job_id)
    if job is None:
        raise DiscoveryJobNotFoundError(f"Job {job_id} not found")
    return DiscoveryJobResponse.model_validate(job)


async def request_stop_for_run(session: AsyncSession, run_id: uuid.UUID) -> DiscoveryRunResponse:
    """Flips `stop_requested` on every non-terminal child job of a run.

    Terminal jobs (already completed/failed/blocked/skipped/stopped) are
    left untouched — there's nothing left for them to honor a stop against.
    """
    run = await discovery_job_repository.get_run(session, run_id)
    if run is None:
        raise DiscoveryRunNotFoundError(f"Run {run_id} not found")

    jobs = await discovery_job_repository.list_jobs_for_run(session, run_id)
    for job in jobs:
        if DiscoveryJobStatus(job.status) not in TERMINAL_JOB_STATUSES:
            await discovery_job_repository.set_stop_requested(session, job.id)

    return await get_run_detail(session, run_id)


# ---- worker-facing façade ---------------------------------------------------


class JobTracker:
    """Reports a single DiscoveryJob's live progress from inside the ARQ
    worker/scraper layer, which has no ambient AsyncSession.

    Opens and commits its own short-lived session per call (mirrors
    lead_repository.upsert_lead's per-lead open/commit/close). A tracking
    write failure is logged and swallowed — it must never take down the
    actual scrape.
    """

    def __init__(self, job_id: uuid.UUID) -> None:
        self.job_id = job_id

    async def mark_running(self, *, message: str | None = None) -> None:
        await self._update_status(status=DiscoveryJobStatus.RUNNING, started_at=_utcnow(), message=message)

    async def mark_completed(self, *, message: str | None = None) -> None:
        await self._update_status(status=DiscoveryJobStatus.COMPLETED, finished_at=_utcnow(), message=message)

    async def mark_failed(self, error: ErrorDetail, *, message: str | None = None) -> None:
        await self._update_status(
            status=DiscoveryJobStatus.FAILED, error=error, finished_at=_utcnow(), message=message
        )

    async def mark_blocked(self, error: ErrorDetail, *, message: str | None = None) -> None:
        await self._update_status(
            status=DiscoveryJobStatus.BLOCKED, error=error, finished_at=_utcnow(), message=message
        )

    async def mark_skipped_cooldown(self, seconds: int, *, message: str | None = None) -> None:
        error = ErrorDetail(
            code="cooldown_skipped",
            message=f"Source is cooling down for {seconds}s — skipping this run",
            retryable=True,
            retry_after_seconds=seconds,
        )
        await self._update_status(
            status=DiscoveryJobStatus.SKIPPED_COOLDOWN, error=error, finished_at=_utcnow(), message=message
        )

    async def mark_stopped(self, *, message: str | None = None) -> None:
        await self._update_status(status=DiscoveryJobStatus.STOPPED, finished_at=_utcnow(), message=message)

    async def update_progress(
        self,
        *,
        current_business_name: str | None = None,
        leads_found_delta: int = 0,
        leads_saved_delta: int = 0,
    ) -> None:
        try:
            async with async_session_factory() as session:
                await discovery_job_repository.update_job_progress(
                    session,
                    self.job_id,
                    current_business_name=current_business_name,
                    leads_found_delta=leads_found_delta,
                    leads_saved_delta=leads_saved_delta,
                )
        except Exception:
            logger.exception("JobTracker: failed to update progress for job %s", self.job_id)

    async def record_event(
        self, event_type: DiscoveryEventType, message: str, *, code: str | None = None, payload: dict | None = None
    ) -> None:
        try:
            async with async_session_factory() as session:
                await discovery_job_repository.insert_event(
                    session, self.job_id, event_type=event_type.value, message=message, code=code, payload=payload
                )
        except Exception:
            logger.exception("JobTracker: failed to record event for job %s", self.job_id)

    async def record_extraction_failure(self, message: str) -> None:
        try:
            async with async_session_factory() as session:
                await discovery_job_repository.update_job_progress(session, self.job_id, extraction_failure_delta=1)
                await discovery_job_repository.insert_event(
                    session, self.job_id, event_type=DiscoveryEventType.WARNING.value, message=message
                )
        except Exception:
            logger.exception("JobTracker: failed to record extraction failure for job %s", self.job_id)

    async def should_stop(self) -> bool:
        try:
            async with async_session_factory() as session:
                return await discovery_job_repository.is_stop_requested(session, self.job_id)
        except Exception:
            # Fail open: a tracking-layer hiccup must not itself abort a job —
            # only an explicit stop request should.
            logger.exception("JobTracker: failed to check stop flag for job %s", self.job_id)
            return False

    async def _update_status(
        self,
        *,
        status: DiscoveryJobStatus,
        error: ErrorDetail | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        message: str | None = None,
    ) -> None:
        try:
            async with async_session_factory() as session:
                await discovery_job_repository.update_job_status(
                    session, self.job_id, status=status, error=error, started_at=started_at, finished_at=finished_at
                )
                if message is not None:
                    await discovery_job_repository.insert_event(
                        session,
                        self.job_id,
                        event_type=DiscoveryEventType.JOB_STATUS_CHANGED.value,
                        message=message,
                        code=error.code if error is not None else None,
                    )
        except Exception:
            logger.exception("JobTracker: failed to update status for job %s", self.job_id)
