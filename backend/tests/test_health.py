from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db_session
from app.main import app


def _override_db_session(mock_session):
    async def _get_db_session():
        yield mock_session

    app.dependency_overrides[get_db_session] = _get_db_session


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.pop(get_db_session, None)


async def test_health_returns_ok_when_database_reachable():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=None)
    _override_db_session(mock_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected"}


async def test_health_returns_503_when_database_unreachable():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("connection failed"))
    _override_db_session(mock_session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 503
