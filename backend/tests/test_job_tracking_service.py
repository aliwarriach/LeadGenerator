import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.discovery_job import DiscoveryJob, DiscoveryJobStatus
from app.services import job_tracking_service
from app.services.job_tracking_service import (
    DiscoveryJobNotFoundError,
    DiscoveryRunNotFoundError,
    JobTracker,
    compute_warnings,
    derive_run_status,
)


class _SessionCM:
    """Fakes `async with async_session_factory() as session: ...` for a
    given mock session, so JobTracker tests can assert on it directly."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _job(**overrides) -> DiscoveryJob:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        source="google_maps",
        query="plumbers",
        location="Karachi, Pakistan",
        status=DiscoveryJobStatus.PENDING,
        current_business_name=None,
        leads_found_session=0,
        leads_saved_session=0,
        extraction_failures_session=0,
        error_code=None,
        error_message=None,
        error_retryable=None,
        error_retry_after_seconds=None,
        stop_requested=False,
        created_at=now,
        started_at=None,
        finished_at=None,
    )
    defaults.update(overrides)
    return DiscoveryJob(**defaults)


# ---- derive_run_status -------------------------------------------------


def test_derive_run_status_empty_jobs_is_pending():
    assert derive_run_status([]) == DiscoveryJobStatus.PENDING


def test_derive_run_status_running_wins_over_everything():
    jobs = [_job(status=DiscoveryJobStatus.COMPLETED), _job(status=DiscoveryJobStatus.RUNNING)]
    assert derive_run_status(jobs) == DiscoveryJobStatus.RUNNING


def test_derive_run_status_pending_when_none_running_but_some_pending():
    jobs = [_job(status=DiscoveryJobStatus.COMPLETED), _job(status=DiscoveryJobStatus.PENDING)]
    assert derive_run_status(jobs) == DiscoveryJobStatus.PENDING


def test_derive_run_status_all_completed_is_completed():
    jobs = [_job(status=DiscoveryJobStatus.COMPLETED), _job(status=DiscoveryJobStatus.COMPLETED)]
    assert derive_run_status(jobs) == DiscoveryJobStatus.COMPLETED


def test_derive_run_status_most_severe_terminal_status_wins():
    jobs = [
        _job(status=DiscoveryJobStatus.COMPLETED),
        _job(status=DiscoveryJobStatus.STOPPED),
        _job(status=DiscoveryJobStatus.FAILED),
    ]
    assert derive_run_status(jobs) == DiscoveryJobStatus.FAILED


# ---- compute_warnings ----------------------------------------------------


def test_compute_warnings_flags_high_failure_rate():
    jobs = [_job(source="facebook", leads_found_session=3, extraction_failures_session=7)]
    warnings = compute_warnings(jobs)
    assert len(warnings) == 1
    assert warnings[0].code == "high_failure_rate"
    assert warnings[0].source == "facebook"


def test_compute_warnings_skips_below_minimum_attempts():
    jobs = [_job(source="facebook", leads_found_session=0, extraction_failures_session=2)]
    assert compute_warnings(jobs) == []


def test_compute_warnings_skips_healthy_jobs():
    jobs = [_job(source="google_maps", leads_found_session=9, extraction_failures_session=1)]
    assert compute_warnings(jobs) == []


# ---- session-based service functions -------------------------------------


async def test_get_run_detail_raises_not_found():
    mock_session = AsyncMock()
    with patch(
        "app.services.job_tracking_service.discovery_job_repository.get_run", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(DiscoveryRunNotFoundError):
            await job_tracking_service.get_run_detail(mock_session, uuid.uuid4())


async def test_get_job_detail_raises_not_found():
    mock_session = AsyncMock()
    with patch(
        "app.services.job_tracking_service.discovery_job_repository.get_job", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(DiscoveryJobNotFoundError):
            await job_tracking_service.get_job_detail(mock_session, uuid.uuid4())


async def test_get_job_detail_includes_total_leads_scraped_by_source():
    mock_session = AsyncMock()
    job = _job(source="google_maps")

    with (
        patch(
            "app.services.job_tracking_service.discovery_job_repository.get_job",
            new=AsyncMock(return_value=job),
        ),
        patch(
            "app.services.job_tracking_service.lead_repository.count_by_source",
            new=AsyncMock(return_value={"google_maps": 57}),
        ),
    ):
        response = await job_tracking_service.get_job_detail(mock_session, job.id)

    assert response.total_leads_scraped_by_source == 57


async def test_request_stop_raises_not_found_when_missing():
    mock_session = AsyncMock()
    with patch(
        "app.services.job_tracking_service.discovery_job_repository.set_stop_requested",
        new=AsyncMock(return_value=None),
    ):
        with pytest.raises(DiscoveryJobNotFoundError):
            await job_tracking_service.request_stop(mock_session, uuid.uuid4())


async def test_request_stop_for_run_raises_not_found_when_run_missing():
    mock_session = AsyncMock()
    with patch(
        "app.services.job_tracking_service.discovery_job_repository.get_run", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(DiscoveryRunNotFoundError):
            await job_tracking_service.request_stop_for_run(mock_session, uuid.uuid4())


async def test_request_stop_for_run_only_stops_non_terminal_jobs():
    mock_session = AsyncMock()
    run_id = uuid.uuid4()
    running_job = _job(run_id=run_id, status=DiscoveryJobStatus.RUNNING)
    pending_job = _job(run_id=run_id, status=DiscoveryJobStatus.PENDING)
    completed_job = _job(run_id=run_id, status=DiscoveryJobStatus.COMPLETED)
    jobs = [running_job, pending_job, completed_job]

    from app.models.discovery_job import DiscoveryRun

    run = DiscoveryRun(id=run_id, total_jobs=3)

    with (
        patch(
            "app.services.job_tracking_service.discovery_job_repository.get_run", new=AsyncMock(return_value=run)
        ),
        patch(
            "app.services.job_tracking_service.discovery_job_repository.list_jobs_for_run",
            new=AsyncMock(return_value=jobs),
        ),
        patch(
            "app.services.job_tracking_service.discovery_job_repository.set_stop_requested", new=AsyncMock()
        ) as mock_set_stop,
        patch(
            "app.services.job_tracking_service.get_run_detail",
            new=AsyncMock(return_value="run-detail"),
        ),
    ):
        result = await job_tracking_service.request_stop_for_run(mock_session, run_id)

    stopped_ids = {call.args[1] for call in mock_set_stop.call_args_list}
    assert stopped_ids == {running_job.id, pending_job.id}
    assert result == "run-detail"


# ---- JobTracker ------------------------------------------------------------


async def test_job_tracker_mark_running_sets_status_and_started_at():
    mock_session = AsyncMock()
    tracker = JobTracker(uuid.uuid4())

    with (
        patch(
            "app.services.job_tracking_service.async_session_factory",
            return_value=_SessionCM(mock_session),
        ),
        patch(
            "app.services.job_tracking_service.discovery_job_repository.update_job_status", new=AsyncMock()
        ) as mock_update,
    ):
        await tracker.mark_running()

    assert mock_update.call_args.kwargs["status"] == DiscoveryJobStatus.RUNNING
    assert isinstance(mock_update.call_args.kwargs["started_at"], datetime)


async def test_job_tracker_should_stop_fails_open_on_error():
    tracker = JobTracker(uuid.uuid4())

    with patch(
        "app.services.job_tracking_service.async_session_factory", side_effect=RuntimeError("db down")
    ):
        result = await tracker.should_stop()

    assert result is False


async def test_job_tracker_should_stop_returns_repository_value():
    mock_session = AsyncMock()
    tracker = JobTracker(uuid.uuid4())

    with (
        patch(
            "app.services.job_tracking_service.async_session_factory",
            return_value=_SessionCM(mock_session),
        ),
        patch(
            "app.services.job_tracking_service.discovery_job_repository.is_stop_requested",
            new=AsyncMock(return_value=True),
        ),
    ):
        result = await tracker.should_stop()

    assert result is True


async def test_job_tracker_record_extraction_failure_updates_progress_and_event():
    mock_session = AsyncMock()
    tracker = JobTracker(uuid.uuid4())

    with (
        patch(
            "app.services.job_tracking_service.async_session_factory",
            return_value=_SessionCM(mock_session),
        ),
        patch(
            "app.services.job_tracking_service.discovery_job_repository.update_job_progress", new=AsyncMock()
        ) as mock_progress,
        patch(
            "app.services.job_tracking_service.discovery_job_repository.insert_event", new=AsyncMock()
        ) as mock_event,
    ):
        await tracker.record_extraction_failure("selector not found")

    assert mock_progress.call_args.kwargs["extraction_failure_delta"] == 1
    assert mock_event.call_args.kwargs["message"] == "selector not found"


async def test_job_tracker_swallows_tracking_failures():
    tracker = JobTracker(uuid.uuid4())

    with patch(
        "app.services.job_tracking_service.async_session_factory", side_effect=RuntimeError("db down")
    ):
        await tracker.mark_completed()  # must not raise
