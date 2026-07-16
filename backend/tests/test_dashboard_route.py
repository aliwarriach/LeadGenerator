from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.dashboard import (
    DashboardActivityResponse,
    DashboardStatsResponse,
    DiscoveryVolumeResponse,
    LeadStageMixResponse,
)
from app.services.lead_service import LeadServiceUnavailableError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_get_stats_returns_200():
    _override_db_session(AsyncMock())
    fake = DashboardStatsResponse(
        discovered_total=100,
        discovered_this_week=10,
        no_website_total=30,
        no_website_pct=30.0,
        audits_completed_total=40,
        audits_completed_this_week=5,
        active_deals=8,
    )
    with patch("app.routes.dashboard.dashboard_service.get_stats", new=AsyncMock(return_value=fake)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/stats")

    assert response.status_code == 200
    assert response.json()["active_deals"] == 8


async def test_get_stats_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())
    with patch(
        "app.routes.dashboard.dashboard_service.get_stats",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("down")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/stats")

    assert response.status_code == 503


async def test_get_discovery_volume_passes_days_query_param():
    _override_db_session(AsyncMock())
    fake = DiscoveryVolumeResponse(days=[], total=0)
    with patch(
        "app.routes.dashboard.dashboard_service.get_discovery_volume", new=AsyncMock(return_value=fake)
    ) as mock_call:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/discovery-volume", params={"days": 14})

    assert response.status_code == 200
    _, kwargs = mock_call.call_args
    assert kwargs["days"] == 14


async def test_get_discovery_volume_rejects_out_of_range_days():
    _override_db_session(AsyncMock())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/dashboard/discovery-volume", params={"days": 500})

    assert response.status_code == 422


async def test_get_lead_stage_mix_returns_200():
    _override_db_session(AsyncMock())
    fake = LeadStageMixResponse(items=[], total=0)
    with patch("app.routes.dashboard.dashboard_service.get_lead_stage_mix", new=AsyncMock(return_value=fake)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/lead-stage-mix")

    assert response.status_code == 200


async def test_list_recent_activity_passes_limit_query_param():
    _override_db_session(AsyncMock())
    fake = DashboardActivityResponse(items=[])
    with patch(
        "app.routes.dashboard.dashboard_service.list_recent_activity", new=AsyncMock(return_value=fake)
    ) as mock_call:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/activity", params={"limit": 5})

    assert response.status_code == 200
    _, kwargs = mock_call.call_args
    assert kwargs["limit"] == 5
