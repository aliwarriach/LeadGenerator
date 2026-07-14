import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.lead import LeadListResponse
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_list_leads_returns_paginated_response():
    _override_db_session(AsyncMock())
    fake_response = LeadListResponse(items=[], total=0, page=1, page_size=20, total_pages=0)

    with patch("app.routes.leads.lead_service.list_leads", new=AsyncMock(return_value=fake_response)):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/leads")

    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0}


async def test_list_leads_passes_query_params_through_to_service():
    _override_db_session(AsyncMock())
    fake_response = LeadListResponse(items=[], total=0, page=2, page_size=5, total_pages=0)

    with patch(
        "app.routes.leads.lead_service.list_leads", new=AsyncMock(return_value=fake_response)
    ) as mock_list:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/leads",
                params={
                    "source": "google_maps",
                    "has_website": "true",
                    "min_rating": 4.0,
                    "niche": "plumbers",
                    "page": 2,
                    "page_size": 5,
                },
            )

    assert response.status_code == 200
    _, kwargs = mock_list.call_args
    assert kwargs["source"] == "google_maps"
    assert kwargs["has_website"] is True
    assert kwargs["min_rating"] == 4.0
    assert kwargs["niche"] == "plumbers"
    assert kwargs["page"] == 2
    assert kwargs["page_size"] == 5


async def test_list_leads_rejects_invalid_page_size():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads", params={"page_size": 500})

    assert response.status_code == 422


async def test_list_leads_rejects_invalid_source():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads", params={"source": "not-a-real-source"})

    assert response.status_code == 422


async def test_get_lead_returns_404_when_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.get_lead",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/leads/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_get_lead_rejects_invalid_uuid():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/leads/not-a-uuid")

    assert response.status_code == 422


async def test_list_leads_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.list_leads",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("Database connection failed")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/leads")

    assert response.status_code == 503


async def test_get_lead_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.leads.lead_service.get_lead",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("Database connection failed")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/leads/{uuid.uuid4()}")

    assert response.status_code == 503
