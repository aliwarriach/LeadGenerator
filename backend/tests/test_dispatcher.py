import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.models.discovery_job import DiscoveryJob
from app.workers import dispatcher


def _job(source: str = "google_maps", **overrides) -> DiscoveryJob:
    defaults = dict(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        source=source,
        query="plumbers",
        location="Karachi, Pakistan",
    )
    defaults.update(overrides)
    return DiscoveryJob(**defaults)


def _fake_arq_job(job_id: str):
    job = AsyncMock()
    job.job_id = job_id
    return job


@asynccontextmanager
async def _session_scope(session):
    yield session


def _patched(claimed, session=None):
    """Patch the session factory and the two repository calls the dispatcher makes."""
    session = session or AsyncMock()
    return (
        patch(
            "app.workers.dispatcher.async_session_factory",
            new=lambda: _session_scope(session),
        ),
        patch(
            "app.workers.dispatcher.discovery_job_repository.claim_pending_jobs",
            new=AsyncMock(return_value=claimed),
        ),
        patch(
            "app.workers.dispatcher.discovery_job_repository.set_arq_job_id", new=AsyncMock()
        ),
        patch(
            "app.workers.dispatcher.job_tracking_service.mark_job_enqueue_failed", new=AsyncMock()
        ),
        session,
    )


async def test_dispatch_pending_jobs_enqueues_claimed_jobs_with_run_min_rating():
    job = _job(source="serper")
    redis = AsyncMock()
    redis.enqueue_job = AsyncMock(return_value=_fake_arq_job(str(job.id)))

    p_factory, p_claim, p_set, p_fail, _ = _patched([(job, 4.5)])
    with p_factory, p_claim as mock_claim, p_set as mock_set, p_fail:
        dispatched = await dispatcher.dispatch_pending_jobs(redis, batch_size=20)

    assert dispatched == 1
    mock_claim.assert_awaited_once()
    assert mock_claim.await_args.kwargs["limit"] == 20

    args, kwargs = redis.enqueue_job.call_args
    assert args[0] == "scrape_serper_job"
    assert args[1] == str(job.id)
    assert args[2] == "plumbers"
    assert args[3] == "Karachi, Pakistan"
    # min_rating comes from the run, not the job row.
    assert args[4] == 4.5
    # Job id doubles as the ARQ id — that's what makes dispatching idempotent.
    assert kwargs["_job_id"] == str(job.id)

    mock_set.assert_awaited_once()
    assert mock_set.await_args.args[2] == str(job.id)


async def test_dispatch_pending_jobs_maps_every_source_to_its_worker_function():
    jobs = [_job(source="google_maps"), _job(source="facebook"), _job(source="serper")]
    redis = AsyncMock()
    redis.enqueue_job = AsyncMock(side_effect=[_fake_arq_job(str(j.id)) for j in jobs])

    p_factory, p_claim, p_set, p_fail, _ = _patched([(j, None) for j in jobs])
    with p_factory, p_claim, p_set, p_fail:
        dispatched = await dispatcher.dispatch_pending_jobs(redis, batch_size=20)

    assert dispatched == 3
    assert [call.args[0] for call in redis.enqueue_job.call_args_list] == [
        "scrape_google_maps_job",
        "scrape_facebook_job",
        "scrape_serper_job",
    ]


async def test_dispatch_pending_jobs_records_id_when_arq_reports_job_already_queued():
    """None from enqueue_job means ARQ already holds this id — the state left
    behind by a crash between enqueueing and recording. Recovering means
    recording the id, not re-enqueueing (which would double-run the scrape)."""
    job = _job()
    redis = AsyncMock()
    redis.enqueue_job = AsyncMock(return_value=None)

    p_factory, p_claim, p_set, p_fail, _ = _patched([(job, None)])
    with p_factory, p_claim, p_set as mock_set, p_fail as mock_fail:
        dispatched = await dispatcher.dispatch_pending_jobs(redis, batch_size=20)

    assert dispatched == 1
    mock_set.assert_awaited_once_with(mock_set.await_args.args[0], job.id, str(job.id))
    mock_fail.assert_not_awaited()


async def test_dispatch_pending_jobs_fails_job_with_unknown_source_without_enqueueing():
    job = _job(source="linkedin")
    redis = AsyncMock()

    p_factory, p_claim, p_set, p_fail, _ = _patched([(job, None)])
    with p_factory, p_claim, p_set as mock_set, p_fail as mock_fail:
        dispatched = await dispatcher.dispatch_pending_jobs(redis, batch_size=20)

    assert dispatched == 0
    redis.enqueue_job.assert_not_called()
    mock_set.assert_not_awaited()
    mock_fail.assert_awaited_once()
    error = mock_fail.await_args.args[2]
    assert error.code == "validation_error"
    assert error.retryable is False


async def test_dispatch_pending_jobs_returns_zero_when_nothing_pending():
    redis = AsyncMock()

    p_factory, p_claim, p_set, p_fail, _ = _patched([])
    with p_factory, p_claim, p_set, p_fail:
        dispatched = await dispatcher.dispatch_pending_jobs(redis, batch_size=20)

    assert dispatched == 0
    redis.enqueue_job.assert_not_called()


async def test_dispatch_pending_jobs_propagates_redis_errors_without_failing_the_job():
    """A Redis outage is transient: the row must stay pending for the next poll
    rather than being marked failed."""
    job = _job()
    redis = AsyncMock()
    redis.enqueue_job = AsyncMock(side_effect=RedisConnectionError("connection refused"))

    p_factory, p_claim, p_set, p_fail, _ = _patched([(job, None)])
    with p_factory, p_claim, p_set as mock_set, p_fail as mock_fail:
        with pytest.raises(RedisConnectionError):
            await dispatcher.dispatch_pending_jobs(redis, batch_size=20)

    mock_set.assert_not_awaited()
    mock_fail.assert_not_awaited()


async def test_run_dispatcher_keeps_polling_after_a_failed_cycle():
    """The loop must survive a transient outage — otherwise one blip silently
    stops all job dispatching until someone notices."""
    settings = type("S", (), {"dispatcher_poll_seconds": 0, "dispatcher_batch_size": 5})()
    redis = AsyncMock()
    cycles = [RedisConnectionError("down"), 1, RuntimeError("stop-loop")]

    with (
        patch("app.workers.dispatcher.get_arq_pool", new=AsyncMock(return_value=redis)),
        patch(
            "app.workers.dispatcher.dispatch_pending_jobs",
            new=AsyncMock(side_effect=cycles),
        ) as mock_dispatch,
    ):
        with pytest.raises(RuntimeError, match="stop-loop"):
            await dispatcher.run_dispatcher(settings)

    # Third call only happens if the RedisConnectionError on the first was
    # swallowed and the loop continued.
    assert mock_dispatch.await_count == 3
    redis.close.assert_awaited_once()
