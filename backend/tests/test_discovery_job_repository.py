import uuid
from unittest.mock import AsyncMock, MagicMock, Mock

from sqlalchemy.dialects import postgresql

from app.models.discovery_job import DiscoveryJob, DiscoveryJobEvent, DiscoveryRun
from app.repositories import discovery_job_repository
from app.repositories.discovery_job_repository import _apply_job_filters
from app.schemas.errors import ErrorDetail
from sqlalchemy import select


async def test_insert_run_adds_commits_and_refreshes():
    mock_session = AsyncMock()
    mock_session.add = Mock()  # AsyncSession.add is synchronous

    run = await discovery_job_repository.insert_run(
        mock_session, country="Pakistan", city="Karachi", custom_niche="plumbers", min_rating=4.0, total_jobs=3
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once_with(run)
    assert isinstance(run, DiscoveryRun)
    assert run.total_jobs == 3


async def test_insert_job_adds_commits_and_refreshes():
    mock_session = AsyncMock()
    mock_session.add = Mock()  # AsyncSession.add is synchronous
    run_id = uuid.uuid4()

    job = await discovery_job_repository.insert_job(
        mock_session, run_id=run_id, source="google_maps", query="plumbers", location="Karachi, Pakistan"
    )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    assert isinstance(job, DiscoveryJob)
    assert job.run_id == run_id


async def test_set_arq_job_id_executes_and_commits():
    mock_session = AsyncMock()

    await discovery_job_repository.set_arq_job_id(mock_session, uuid.uuid4(), "arq-123")

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


def test_apply_job_filters_with_no_filters_leaves_statement_unfiltered():
    stmt = _apply_job_filters(select(DiscoveryJob), status=None, source=None, run_id=None)
    assert "WHERE" not in str(stmt)


def test_apply_job_filters_combines_all_filters():
    stmt = _apply_job_filters(select(DiscoveryJob), status="running", source="facebook", run_id=uuid.uuid4())
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "discovery_jobs.status" in compiled
    assert "discovery_jobs.source" in compiled
    assert "discovery_jobs.run_id" in compiled


async def test_update_job_progress_skips_query_when_no_deltas_or_name():
    mock_session = AsyncMock()

    await discovery_job_repository.update_job_progress(mock_session, uuid.uuid4())

    mock_session.execute.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


async def test_update_job_progress_executes_when_delta_given():
    mock_session = AsyncMock()

    await discovery_job_repository.update_job_progress(mock_session, uuid.uuid4(), leads_saved_delta=1)

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()


async def test_update_job_status_includes_error_fields_when_error_given():
    mock_session = AsyncMock()
    error = ErrorDetail(code="blocked_captcha", message="captcha", retryable=True, retry_after_seconds=1800)

    await discovery_job_repository.update_job_status(mock_session, uuid.uuid4(), status="blocked", error=error)

    stmt = mock_session.execute.call_args.args[0]
    compiled_params = stmt.compile().params
    assert compiled_params["error_code"] == "blocked_captcha"
    assert compiled_params["error_retry_after_seconds"] == 1800


async def test_claim_pending_jobs_returns_job_and_run_min_rating_pairs():
    mock_session = AsyncMock()
    job = MagicMock(spec=DiscoveryJob)
    result = MagicMock()
    result.all.return_value = [(job, 4.5)]
    mock_session.execute = AsyncMock(return_value=result)

    claimed = await discovery_job_repository.claim_pending_jobs(mock_session, limit=20)

    assert claimed == [(job, 4.5)]


async def test_claim_pending_jobs_selects_only_undispatched_pending_rows_with_skip_locked():
    mock_session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)

    await discovery_job_repository.claim_pending_jobs(mock_session, limit=5)

    compiled = str(mock_session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    # arq_job_id IS NULL is the "not yet dispatched" marker — without it the
    # dispatcher would re-enqueue jobs already sitting in the queue.
    assert "discovery_jobs.arq_job_id IS NULL" in compiled
    assert "discovery_jobs.status =" in compiled
    # min_rating lives on the run, so it has to be joined rather than re-queried.
    assert "JOIN discovery_runs" in compiled
    assert "discovery_runs.min_rating" in compiled
    # SKIP LOCKED is what keeps a second dispatcher from handing out duplicates.
    assert "FOR UPDATE OF discovery_jobs SKIP LOCKED" in compiled


async def test_list_jobs_for_recent_runs_returns_scalars():
    mock_session = AsyncMock()
    jobs = [MagicMock(spec=DiscoveryJob), MagicMock(spec=DiscoveryJob)]
    result = MagicMock()
    result.scalars.return_value.all.return_value = jobs
    mock_session.execute = AsyncMock(return_value=result)

    returned = await discovery_job_repository.list_jobs_for_recent_runs(mock_session, run_limit=200)

    mock_session.execute.assert_awaited_once()
    assert returned == jobs


async def test_list_jobs_for_recent_runs_scopes_by_recent_run_ids_subquery():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)

    await discovery_job_repository.list_jobs_for_recent_runs(mock_session, run_limit=50)

    stmt = mock_session.execute.call_args.args[0]
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "discovery_jobs.run_id IN" in compiled
    assert "discovery_runs.created_at" in compiled


async def test_set_stop_requested_returns_none_when_job_missing():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    job = await discovery_job_repository.set_stop_requested(mock_session, uuid.uuid4())

    assert job is None
    mock_session.commit.assert_awaited_once()


async def test_set_stop_requested_returns_updated_job():
    mock_session = AsyncMock()
    fake_job = DiscoveryJob(stop_requested=True)
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_job
    mock_session.execute = AsyncMock(return_value=result)

    job = await discovery_job_repository.set_stop_requested(mock_session, uuid.uuid4())

    assert job is fake_job


async def test_list_events_applies_after_cursor():
    mock_session = AsyncMock()
    fake_events = [DiscoveryJobEvent(id=5, message="m")]
    result = MagicMock()
    result.scalars.return_value.all.return_value = fake_events
    mock_session.execute = AsyncMock(return_value=result)

    events = await discovery_job_repository.list_events(mock_session, uuid.uuid4(), after=3, limit=50)

    assert events == fake_events
    stmt = mock_session.execute.call_args.args[0]
    assert "id > " in str(stmt) or "id >" in str(stmt)
