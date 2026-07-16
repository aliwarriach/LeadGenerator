import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db_session
from app.main import app
from app.schemas.activity import ActivityListResponse, ActivityResponse
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_create_activity_returns_200_with_activity():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    fake_response = ActivityResponse(
        id=1, lead_id=lead_id, type="email", description="Cold email generated",
        created_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.routes.activities.activity_service.create_activity", new=AsyncMock(return_value=fake_response)
    ) as mock_create:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/activities/{lead_id}", json={"type": "email", "description": "Cold email generated"}
            )

    assert response.status_code == 200
    assert response.json()["description"] == "Cold email generated"
    _, kwargs = mock_create.call_args
    assert kwargs["type"] == "email"
    assert kwargs["description"] == "Cold email generated"


async def test_create_activity_rejects_invalid_type():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/activities/{uuid.uuid4()}", json={"type": "not-a-type", "description": "x"}
        )

    assert response.status_code == 422


async def test_create_activity_rejects_empty_description():
    _override_db_session(AsyncMock())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/activities/{uuid.uuid4()}", json={"type": "email", "description": ""})

    assert response.status_code == 422


async def test_create_activity_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.activities.activity_service.create_activity",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/activities/{uuid.uuid4()}", json={"type": "email", "description": "x"}
            )

    assert response.status_code == 404


async def test_create_activity_returns_503_when_db_unavailable():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.activities.activity_service.create_activity",
        new=AsyncMock(side_effect=LeadServiceUnavailableError("db down")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/activities/{uuid.uuid4()}", json={"type": "email", "description": "x"}
            )

    assert response.status_code == 503


async def test_list_activities_returns_200_with_items_latest_first():
    _override_db_session(AsyncMock())
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_response = ActivityListResponse(
        lead_id=lead_id,
        items=[
            ActivityResponse(id=2, lead_id=lead_id, type="stage_change", description="Moved to Won", created_at=now),
            ActivityResponse(id=1, lead_id=lead_id, type="email", description="Cold email generated", created_at=now),
        ],
    )

    with patch(
        "app.routes.activities.activity_service.list_activities", new=AsyncMock(return_value=fake_response)
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/activities/{lead_id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["description"] == "Moved to Won"


async def test_list_activities_returns_404_when_lead_not_found():
    _override_db_session(AsyncMock())

    with patch(
        "app.routes.activities.activity_service.list_activities",
        new=AsyncMock(side_effect=LeadNotFoundError("not found")),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/activities/{uuid.uuid4()}")

    assert response.status_code == 404
