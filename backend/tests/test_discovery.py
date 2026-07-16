import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.routes.discovery import get_redis_pool
from app.schemas.discovery import DiscoveryJobRef, DiscoveryResponse
from app.schemas.discovery_job import DiscoveryJobResponse
from app.services.discovery_service import DiscoveryQueueError
from app.services.job_tracking_service import DiscoveryJobNotFoundError, DiscoveryRunNotFoundError


def _override_redis(mock_redis):
    async def _get_redis_pool():
        return mock_redis

    app.dependency_overrides[get_redis_pool] = _get_redis_pool


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_redis_pool, None)
    app.dependency_overrides.pop(get_db_session, None)


def _payload(**overrides) -> dict:
    payload = {
        "country": "Pakistan",
        "city": "Karachi",
        "custom_niche": "plumbers",
    }
    payload.update(overrides)
    return payload


def _fake_response(**overrides) -> DiscoveryResponse:
    defaults = dict(
        run_id=uuid.uuid4(),
        country="Pakistan",
        city="Karachi",
        custom_niche="plumbers",
        min_rating=None,
        jobs=[
            DiscoveryJobRef(source="google_maps", city="Karachi", job_id=uuid.uuid4()),
            DiscoveryJobRef(source="facebook", city="Karachi", job_id=uuid.uuid4()),
            DiscoveryJobRef(source="serper", city="Karachi", job_id=uuid.uuid4()),
        ],
    )
    defaults.update(overrides)
    return DiscoveryResponse(**defaults)


async def test_start_discovery_returns_202_with_run_and_jobs():
    _override_redis(AsyncMock())
    _override_db_session(AsyncMock())
    fake_response = _fake_response()

    with patch(
        "app.routes.discovery.discovery_service.start_discovery", new=AsyncMock(return_value=fake_response)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/start-discovery", json=_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["run_id"] == str(fake_response.run_id)
    assert {job["source"] for job in body["jobs"]} == {"google_maps", "facebook", "serper"}


async def test_start_discovery_returns_503_when_enqueue_fails():
    _override_redis(AsyncMock())
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.discovery.discovery_service.start_discovery",
        new=AsyncMock(side_effect=DiscoveryQueueError("could not queue")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/start-discovery", json=_payload())

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "queue_unavailable"


async def test_start_discovery_rejects_empty_custom_niche():
    _override_redis(AsyncMock())
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload(custom_niche=""))

    assert response.status_code == 422


async def test_start_discovery_rejects_missing_country():
    _override_redis(AsyncMock())
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/start-discovery", json={"city": "Karachi", "custom_niche": "plumbers"}
        )

    assert response.status_code == 422


async def test_start_discovery_rejects_out_of_range_min_rating():
    _override_redis(AsyncMock())
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload(min_rating=5.5))

    assert response.status_code == 422


async def test_start_discovery_rejects_too_many_cities():
    _override_redis(AsyncMock())
    _override_db_session(AsyncMock())
    too_many_cities = ", ".join(f"City{i}" for i in range(11))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload(city=too_many_cities))

    assert response.status_code == 422


async def test_get_job_status_returns_200_for_known_job():
    _override_db_session(AsyncMock())
    job_id = uuid.uuid4()
    fake_job = DiscoveryJobResponse(
        id=job_id,
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

    with patch(
        "app.routes.discovery.job_tracking_service.get_job_detail", new=AsyncMock(return_value=fake_job)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/discovery-jobs/{job_id}")

    assert response.status_code == 200
    assert response.json()["status"] == "running"


async def test_get_job_status_returns_404_for_unknown_job():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.discovery.job_tracking_service.get_job_detail",
        new=AsyncMock(side_effect=DiscoveryJobNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/discovery-jobs/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


async def test_get_job_status_rejects_invalid_uuid():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/discovery-jobs/not-a-uuid")

    assert response.status_code == 422


def _fake_job_response(**overrides) -> DiscoveryJobResponse:
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


async def test_stop_job_returns_updated_job():
    _override_db_session(AsyncMock())
    job_id = uuid.uuid4()
    fake_job = _fake_job_response(id=job_id, stop_requested=True)

    with patch(
        "app.routes.discovery.job_tracking_service.request_stop", new=AsyncMock(return_value=fake_job)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/discovery-jobs/{job_id}/stop")

    assert response.status_code == 200
    assert response.json()["stop_requested"] is True


async def test_stop_job_returns_404_when_missing():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.discovery.job_tracking_service.request_stop",
        new=AsyncMock(side_effect=DiscoveryJobNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/discovery-jobs/{uuid.uuid4()}/stop")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "job_not_found"


async def test_stop_run_returns_404_when_missing():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.discovery.job_tracking_service.request_stop_for_run",
        new=AsyncMock(side_effect=DiscoveryRunNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(f"/discovery-runs/{uuid.uuid4()}/stop")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"
