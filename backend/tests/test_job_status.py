from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from arq.jobs import JobDef, JobResult, JobStatus

from app.services import discovery_service
from app.services.discovery_service import JobNotFoundError


async def test_get_job_status_raises_not_found_for_unknown_job():
    mock_redis = AsyncMock()
    mock_job = AsyncMock()
    mock_job.status = AsyncMock(return_value=JobStatus.not_found)

    with patch("app.services.discovery_service.Job", return_value=mock_job):
        with pytest.raises(JobNotFoundError):
            await discovery_service.get_job_status(mock_redis, "missing-job")


async def test_get_job_status_returns_queued_before_start():
    mock_redis = AsyncMock()
    mock_job = AsyncMock()
    mock_job.status = AsyncMock(return_value=JobStatus.queued)
    mock_job.result_info = AsyncMock(return_value=None)
    enqueue_time = datetime.now(timezone.utc)
    mock_job.info = AsyncMock(
        return_value=JobDef(
            function="scrape_google_maps_job",
            args=("plumbers", "Karachi, Pakistan"),
            kwargs={},
            job_try=1,
            enqueue_time=enqueue_time,
            score=None,
            job_id="job-1",
        )
    )

    with patch("app.services.discovery_service.Job", return_value=mock_job):
        result = await discovery_service.get_job_status(mock_redis, "job-1")

    assert result.status == "queued"
    assert result.function == "scrape_google_maps_job"
    assert result.enqueue_time == enqueue_time
    assert result.result is None
    assert result.success is None


async def test_get_job_status_returns_success_result():
    mock_redis = AsyncMock()
    mock_job = AsyncMock()
    mock_job.status = AsyncMock(return_value=JobStatus.complete)
    now = datetime.now(timezone.utc)
    mock_job.result_info = AsyncMock(
        return_value=JobResult(
            function="scrape_google_maps_job",
            args=("plumbers", "Karachi, Pakistan"),
            kwargs={},
            job_try=1,
            enqueue_time=now,
            score=None,
            success=True,
            result={"source": "google_maps", "query": "plumbers", "scraped": 10, "saved": 9},
            start_time=now,
            finish_time=now,
            queue_name="arq:queue",
            job_id="job-1",
        )
    )

    with patch("app.services.discovery_service.Job", return_value=mock_job):
        result = await discovery_service.get_job_status(mock_redis, "job-1")

    assert result.status == "complete"
    assert result.success is True
    assert result.result == {"source": "google_maps", "query": "plumbers", "scraped": 10, "saved": 9}
    assert result.error is None


async def test_get_job_status_returns_error_on_failure():
    mock_redis = AsyncMock()
    mock_job = AsyncMock()
    mock_job.status = AsyncMock(return_value=JobStatus.complete)
    now = datetime.now(timezone.utc)
    mock_job.result_info = AsyncMock(
        return_value=JobResult(
            function="scrape_google_maps_job",
            args=(),
            kwargs={},
            job_try=3,
            enqueue_time=now,
            score=None,
            success=False,
            result=RuntimeError("boom"),
            start_time=now,
            finish_time=now,
            queue_name="arq:queue",
            job_id="job-1",
        )
    )

    with patch("app.services.discovery_service.Job", return_value=mock_job):
        result = await discovery_service.get_job_status(mock_redis, "job-1")

    assert result.status == "complete"
    assert result.success is False
    assert result.result is None
    assert "boom" in result.error
