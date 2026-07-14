import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.lead import Lead
from app.services import lead_service
from app.services.lead_service import LeadNotFoundError, LeadServiceUnavailableError


def _lead(**overrides) -> Lead:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        name="Bahu Plumbers",
        location="Karachi",
        website=None,
        website_domain=None,
        phone=None,
        source="google_maps",
        has_website=False,
        rating=None,
        category=None,
        query="plumbers",
        search_location="Karachi, Pakistan",
        website_score=None,
        website_score_details=None,
        emails=None,
        tech_stack=None,
        is_registered=None,
        logo_valid=None,
        enriched_at=None,
        raw_data={},
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Lead(**defaults)


def _list_kwargs(**overrides) -> dict:
    defaults = dict(
        source=None,
        has_website=None,
        min_rating=None,
        min_website_score=None,
        name=None,
        search_location=None,
        niche=None,
        sort_by="created_at",
        sort_order="desc",
        page=1,
        page_size=20,
    )
    defaults.update(overrides)
    return defaults


async def test_list_leads_computes_pagination_metadata():
    mock_session = AsyncMock()
    leads = [_lead(name="A"), _lead(name="B")]

    with patch(
        "app.services.lead_service.lead_repository.list_leads",
        new=AsyncMock(return_value=(leads, 42)),
    ) as mock_list:
        response = await lead_service.list_leads(mock_session, **_list_kwargs(page=3, page_size=10))

    assert response.total == 42
    assert response.page == 3
    assert response.page_size == 10
    assert response.total_pages == 5  # ceil(42/10)
    assert len(response.items) == 2

    _, kwargs = mock_list.call_args
    assert kwargs["offset"] == 20  # (page - 1) * page_size
    assert kwargs["limit"] == 10


async def test_list_leads_zero_total_pages_when_no_results():
    mock_session = AsyncMock()

    with patch(
        "app.services.lead_service.lead_repository.list_leads",
        new=AsyncMock(return_value=([], 0)),
    ):
        response = await lead_service.list_leads(mock_session, **_list_kwargs())

    assert response.total_pages == 0
    assert response.items == []


async def test_get_lead_returns_response_when_found():
    mock_session = AsyncMock()
    lead = _lead()

    with patch(
        "app.services.lead_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ):
        response = await lead_service.get_lead(mock_session, lead.id)

    assert response.id == lead.id
    assert response.name == "Bahu Plumbers"


async def test_get_lead_raises_not_found_when_missing():
    mock_session = AsyncMock()

    with patch(
        "app.services.lead_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(LeadNotFoundError):
            await lead_service.get_lead(mock_session, uuid.uuid4())


async def test_list_leads_raises_service_unavailable_on_db_failure():
    mock_session = AsyncMock()

    with patch(
        "app.services.lead_service.lead_repository.list_leads",
        new=AsyncMock(side_effect=ConnectionRefusedError("db unreachable")),
    ):
        with pytest.raises(LeadServiceUnavailableError):
            await lead_service.list_leads(mock_session, **_list_kwargs())


async def test_get_lead_raises_service_unavailable_on_db_failure():
    mock_session = AsyncMock()

    with patch(
        "app.services.lead_service.lead_repository.get_by_id",
        new=AsyncMock(side_effect=ConnectionRefusedError("db unreachable")),
    ):
        with pytest.raises(LeadServiceUnavailableError):
            await lead_service.get_lead(mock_session, uuid.uuid4())
