import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.discovery_job import (
    DiscoveryJobEventListResponse,
    DiscoveryJobEventResponse,
    DiscoveryJobListResponse,
    DiscoveryJobResponse,
    DiscoveryRunListResponse,
    DiscoveryRunResponse,
    DiscoveryRunSummary,
)
from app.services.job_tracking_service import DiscoveryJobNotFoundError, DiscoveryRunNotFoundError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


def _job(**overrides) -> DiscoveryJobResponse:
    defaults = dict(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        source="google_maps",
        query="plumbers",
        location="Karachi, Pakistan",
        status="running",
        current_business_name=None,
        leads_found_session=0,
        leads_saved_session=0,
        extraction_failures_session=0,
        error_code=None,
        error_message=None,
        error_retryable=None,
        error_retry_after_seconds=None,
        stop_requested=False,
        created_at="2026-07-15T00:00:00+00:00",
        started_at=None,
        finished_at=None,
    )
    defaults.update(overrides)
    return DiscoveryJobResponse(**defaults)


async def test_list_runs_returns_paginated_response():
    _override_db_session(AsyncMock())
    fake_response = DiscoveryRunListResponse(items=[], total=0, page=1, page_size=20, total_pages=0)

    with patch("app.routes.discovery.job_tracking_service.list_runs", new=AsyncMock(return_value=fake_response)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/discovery-runs")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}


async def test_list_runs_returns_items_when_present():
    _override_db_session(AsyncMock())
    summary = DiscoveryRunSummary(
        id=uuid.uuid4(),
        country="Pakistan",
        city="Karachi",
        custom_niche="plumbers",
        min_rating=None,
        created_at="2026-07-15T00:00:00+00:00",
        status="completed",
    )
    fake_response = DiscoveryRunListResponse(items=[summary], total=1, page=1, page_size=20, total_pages=1)

    with patch("app.routes.discovery.job_tracking_service.list_runs", new=AsyncMock(return_value=fake_response)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/discovery-runs")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "completed"


async def test_get_run_stats_returns_200_and_is_not_shadowed_by_run_id_route():
    _override_db_session(AsyncMock())
    from app.schemas.discovery_job import DiscoveryRunStatsResponse, SourcePerformance

    fake_stats = DiscoveryRunStatsResponse(
        completed_run_count=3,
        avg_duration_seconds=245.5,
        avg_leads_saved=12.0,
        total_leads_saved=36,
        success_rate=0.75,
        leads_by_source=[SourcePerformance(source="google_maps", avg_leads_saved=8.0)],
    )

    with patch("app.routes.discovery.job_tracking_service.get_run_stats", new=AsyncMock(return_value=fake_stats)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/discovery-runs/stats")

    # A regression here (e.g. /discovery-runs/stats registered after
    # /discovery-runs/{run_id}) would 422 instead, since "stats" fails UUID
    # parsing as a run_id path param.
    assert response.status_code == 200
    assert response.json() == {
        "completed_run_count": 3,
        "avg_duration_seconds": 245.5,
        "avg_leads_saved": 12.0,
        "total_leads_saved": 36,
        "success_rate": 0.75,
        "leads_by_source": [{"source": "google_maps", "avg_leads_saved": 8.0}],
    }


async def test_get_run_detail_returns_200_with_jobs_and_warnings():
    _override_db_session(AsyncMock())
    run_id = uuid.uuid4()
    fake_run = DiscoveryRunResponse(
        id=run_id,
        country="Pakistan",
        city="Karachi",
        custom_niche="plumbers",
        min_rating=None,
        created_at="2026-07-15T00:00:00+00:00",
        status="running",
        started_at=None,
        finished_at=None,
        warnings=[],
        jobs=[_job(run_id=run_id)],
    )

    with patch(
        "app.routes.discovery.job_tracking_service.get_run_detail", new=AsyncMock(return_value=fake_run)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/discovery-runs/{run_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert len(body["jobs"]) == 1


async def test_get_run_detail_returns_404_when_missing():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.discovery.job_tracking_service.get_run_detail",
        new=AsyncMock(side_effect=DiscoveryRunNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/discovery-runs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"


async def test_list_jobs_passes_filters_through_to_service():
    _override_db_session(AsyncMock())
    fake_response = DiscoveryJobListResponse(items=[], total=0, page=1, page_size=20, total_pages=0)

    with patch(
        "app.routes.discovery.job_tracking_service.list_jobs", new=AsyncMock(return_value=fake_response)
    ) as mock_list:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/discovery-jobs", params={"status": "blocked", "source": "facebook", "page": 2, "page_size": 5}
            )

    assert response.status_code == 200
    _, kwargs = mock_list.call_args
    assert kwargs["status"] == "blocked"
    assert kwargs["source"] == "facebook"
    assert kwargs["page"] == 2
    assert kwargs["page_size"] == 5


async def test_list_jobs_rejects_invalid_status():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/discovery-jobs", params={"status": "not-a-real-status"})

    assert response.status_code == 422


async def test_list_job_events_returns_items_and_next_cursor():
    _override_db_session(AsyncMock())
    job_id = uuid.uuid4()
    fake_response = DiscoveryJobEventListResponse(
        items=[
            DiscoveryJobEventResponse(
                id=5,
                job_id=job_id,
                event_type="lead_saved",
                code=None,
                message='Added new lead "A"',
                payload=None,
                created_at="2026-07-15T00:00:00+00:00",
            )
        ],
        next_cursor=5,
    )

    with patch(
        "app.routes.discovery.job_tracking_service.list_job_events", new=AsyncMock(return_value=fake_response)
    ) as mock_events:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/discovery-jobs/{job_id}/events", params={"after": 2, "limit": 50})

    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] == 5
    assert len(body["items"]) == 1
    _, kwargs = mock_events.call_args
    assert kwargs["after"] == 2
    assert kwargs["limit"] == 50


async def test_list_job_events_returns_404_when_job_missing():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.discovery.job_tracking_service.list_job_events",
        new=AsyncMock(side_effect=DiscoveryJobNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/discovery-jobs/{uuid.uuid4()}/events")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"
