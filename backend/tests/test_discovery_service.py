import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.models.discovery_job import DiscoveryJob, DiscoveryRun
from app.schemas.discovery import DiscoveryRequest
from app.services import discovery_service
from app.services.discovery_service import DiscoveryQueueError


def _request(**overrides) -> DiscoveryRequest:
    defaults = dict(country="Pakistan", city="Karachi", custom_niche="plumbers")
    defaults.update(overrides)
    return DiscoveryRequest(**defaults)


def _fake_arq_job(job_id: str):
    job = AsyncMock()
    job.job_id = job_id
    return job


def _patched_tracking(run_id=None, job_ids=None):
    run = DiscoveryRun(id=run_id or uuid.uuid4(), total_jobs=3)
    job_ids = iter(job_ids or [uuid.uuid4() for _ in range(20)])

    async def _create_job(session, *, run_id, source, query, location):
        return DiscoveryJob(id=next(job_ids), run_id=run_id, source=source, query=query, location=location)

    return (
        patch("app.services.discovery_service.job_tracking_service.create_run", new=AsyncMock(return_value=run)),
        patch("app.services.discovery_service.job_tracking_service.create_job", new=AsyncMock(side_effect=_create_job)),
        patch("app.services.discovery_service.job_tracking_service.attach_arq_job_id", new=AsyncMock()),
        patch("app.services.discovery_service.job_tracking_service.mark_job_enqueue_failed", new=AsyncMock()),
        run,
    )


async def test_start_discovery_creates_run_and_job_row_per_fan_out_before_enqueue():
    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(
        side_effect=[_fake_arq_job(f"arq-{i}") for i in range(3)]
    )

    p_run, p_job, p_attach, p_fail, run = _patched_tracking()
    with p_run, p_job as mock_create_job, p_attach as mock_attach, p_fail:
        response = await discovery_service.start_discovery(mock_redis, mock_session, _request())

    assert response.run_id == run.id
    assert mock_create_job.await_count == 3
    assert mock_attach.await_count == 3
    assert {job.source for job in response.jobs} == {"google_maps", "facebook", "serper"}
    assert mock_redis.enqueue_job.call_count == 3
    # Enqueue call is keyed by our own job row id, not a niche/location tuple directly.
    first_call_args = mock_redis.enqueue_job.call_args_list[0].args
    assert first_call_args[0] == "scrape_google_maps_job"
    assert first_call_args[2] == "plumbers"
    assert first_call_args[3] == "Karachi, Pakistan"


async def test_start_discovery_fans_out_per_city():
    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(side_effect=[_fake_arq_job(f"arq-{i}") for i in range(6)])

    p_run, p_job, p_attach, p_fail, run = _patched_tracking()
    with p_run, p_job, p_attach, p_fail:
        response = await discovery_service.start_discovery(
            mock_redis, mock_session, _request(city="Lahore, Karachi", min_rating=4.5)
        )

    assert len(response.jobs) == 6
    assert {job.city for job in response.jobs} == {"Lahore", "Karachi"}


async def test_start_discovery_marks_job_failed_and_raises_when_enqueue_fails():
    mock_session = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=None)

    p_run, p_job, p_attach, p_fail, run = _patched_tracking()
    with p_run, p_job, p_attach, p_fail as mock_fail:
        with pytest.raises(DiscoveryQueueError):
            await discovery_service.start_discovery(mock_redis, mock_session, _request())

    mock_fail.assert_awaited_once()
    assert mock_fail.call_args.args[2].code == "queue_unavailable"
