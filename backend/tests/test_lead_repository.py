import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.lead import Lead
from app.repositories import lead_repository
from app.repositories.lead_repository import _apply_lead_filters


def test_apply_lead_filters_with_no_filters_leaves_statement_unfiltered():
    stmt = _apply_lead_filters(
        select(Lead),
        source=None,
        has_website=None,
        min_rating=None,
        min_website_score=None,
        name_contains=None,
        search_location_contains=None,
        niche_equals=None,
    )
    assert "WHERE" not in str(stmt)


def test_apply_lead_filters_combines_all_filters():
    stmt = _apply_lead_filters(
        select(Lead),
        source="google_maps",
        has_website=True,
        min_rating=4.0,
        min_website_score=70.0,
        name_contains="plumb",
        search_location_contains="karachi",
        niche_equals="plumbers",
    )
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "leads.source" in compiled
    assert "leads.has_website" in compiled
    assert "leads.rating" in compiled
    assert "leads.website_score" in compiled
    assert "leads.name ILIKE" in compiled
    assert "leads.search_location ILIKE" in compiled
    assert "leads.query" in compiled


async def test_list_leads_returns_items_and_total_count():
    mock_session = AsyncMock()
    fake_leads = [Lead(name="A"), Lead(name="B")]

    count_result = MagicMock()
    count_result.scalar_one.return_value = 42
    items_result = MagicMock()
    items_result.scalars.return_value.all.return_value = fake_leads
    mock_session.execute = AsyncMock(side_effect=[count_result, items_result])

    items, total = await lead_repository.list_leads(mock_session, limit=2, offset=0)

    assert total == 42
    assert items == fake_leads
    assert mock_session.execute.call_count == 2


async def test_get_by_id_returns_none_when_not_found():
    mock_session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.get_by_id(mock_session, uuid.uuid4())
    assert lead is None


async def test_get_by_id_returns_lead_when_found():
    mock_session = AsyncMock()
    fake_lead = Lead(name="Bahu Plumbers")
    result = MagicMock()
    result.scalar_one_or_none.return_value = fake_lead
    mock_session.execute = AsyncMock(return_value=result)

    lead = await lead_repository.get_by_id(mock_session, uuid.uuid4())
    assert lead is fake_lead
