from unittest.mock import AsyncMock, patch

import pytest
from arq.jobs import JobStatus
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routes.discovery import get_redis_pool


def _override_redis(mock_redis):
    async def _get_redis_pool():
        return mock_redis

    app.dependency_overrides[get_redis_pool] = _get_redis_pool


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_redis_pool, None)


def _fake_job(job_id: str):
    job = AsyncMock()
    job.job_id = job_id
    return job


def _payload(**overrides) -> dict:
    payload = {
        "country": "Pakistan",
        "city": "Karachi",
        "custom_niche": "plumbers",
    }
    payload.update(overrides)
    return payload


async def test_start_discovery_queues_all_scrapers_for_single_city():
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(
        side_effect=[_fake_job("job-gmaps-1"), _fake_job("job-fb-1"), _fake_job("job-serper-1")]
    )
    _override_redis(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["country"] == "Pakistan"
    assert body["city"] == "Karachi"
    assert body["custom_niche"] == "plumbers"
    assert body["min_rating"] is None
    assert {job["source"] for job in body["jobs"]} == {"google_maps", "facebook", "serper"}
    assert all(job["city"] == "Karachi" for job in body["jobs"])

    assert mock_redis.enqueue_job.call_count == 3
    mock_redis.enqueue_job.assert_any_call("scrape_google_maps_job", "plumbers", "Karachi, Pakistan", None)
    mock_redis.enqueue_job.assert_any_call("scrape_facebook_job", "plumbers", "Karachi, Pakistan", None)
    mock_redis.enqueue_job.assert_any_call("scrape_serper_job", "plumbers", "Karachi, Pakistan", None)


async def test_start_discovery_fans_out_per_city_with_min_rating():
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(side_effect=[_fake_job(f"job-{i}") for i in range(6)])
    _override_redis(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/start-discovery", json=_payload(city="Lahore, Karachi", min_rating=4.5)
        )

    assert response.status_code == 202
    body = response.json()
    assert body["min_rating"] == 4.5
    assert len(body["jobs"]) == 6
    assert {job["city"] for job in body["jobs"]} == {"Lahore", "Karachi"}

    assert mock_redis.enqueue_job.call_count == 6
    mock_redis.enqueue_job.assert_any_call("scrape_google_maps_job", "plumbers", "Lahore, Pakistan", 4.5)
    mock_redis.enqueue_job.assert_any_call("scrape_google_maps_job", "plumbers", "Karachi, Pakistan", 4.5)


async def test_start_discovery_returns_503_when_enqueue_fails():
    mock_redis = AsyncMock()
    mock_redis.enqueue_job = AsyncMock(return_value=None)
    _override_redis(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload())

    assert response.status_code == 503


async def test_start_discovery_rejects_empty_custom_niche():
    mock_redis = AsyncMock()
    _override_redis(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload(custom_niche=""))

    assert response.status_code == 422


async def test_start_discovery_rejects_missing_country():
    mock_redis = AsyncMock()
    _override_redis(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/start-discovery", json={"city": "Karachi", "custom_niche": "plumbers"}
        )

    assert response.status_code == 422


async def test_start_discovery_rejects_out_of_range_min_rating():
    mock_redis = AsyncMock()
    _override_redis(mock_redis)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload(min_rating=5.5))

    assert response.status_code == 422


async def test_start_discovery_rejects_too_many_cities():
    mock_redis = AsyncMock()
    _override_redis(mock_redis)
    too_many_cities = ", ".join(f"City{i}" for i in range(11))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/start-discovery", json=_payload(city=too_many_cities))

    assert response.status_code == 422


async def test_get_job_status_returns_200_for_known_job():
    mock_redis = AsyncMock()
    _override_redis(mock_redis)
    mock_job = AsyncMock()
    mock_job.status = AsyncMock(return_value=JobStatus.in_progress)
    mock_job.result_info = AsyncMock(return_value=None)
    mock_job.info = AsyncMock(return_value=None)

    with patch("app.services.discovery_service.Job", return_value=mock_job):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/discovery-jobs/some-job-id")

    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"


async def test_get_job_status_returns_404_for_unknown_job():
    mock_redis = AsyncMock()
    _override_redis(mock_redis)
    mock_job = AsyncMock()
    mock_job.status = AsyncMock(return_value=JobStatus.not_found)

    with patch("app.services.discovery_service.Job", return_value=mock_job):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/discovery-jobs/unknown-job-id")

    assert response.status_code == 404
