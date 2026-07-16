import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.activity import Activity, ActivityType
from app.models.lead import Lead
from app.services import activity_service
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
        estimated_revenue_level=None,
        pipeline_stage="contacted",
        query=None,
        search_location=None,
        website_score=None,
        website_score_details=None,
        pagespeed_score=None,
        seo_score=None,
        performance_issues=None,
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


async def test_change_lead_stage_updates_pipeline_and_logs_activity():
    mock_session = AsyncMock()
    lead = _lead(pipeline_stage="contacted")

    with patch(
        "app.services.activity_service.lead_repository.update_lead_pipeline", new=AsyncMock(return_value=lead)
    ), patch(
        "app.services.activity_service.activity_repository.add_activity", new=AsyncMock()
    ) as mock_add_activity:
        response = await activity_service.change_lead_stage(mock_session, lead.id, "contacted")

    assert response.pipeline_stage == "contacted"
    _, kwargs = mock_add_activity.call_args
    assert kwargs["type"] == ActivityType.STAGE_CHANGE
    assert kwargs["description"] == "Moved to Contacted"


async def test_change_lead_stage_raises_not_found_when_lead_missing():
    mock_session = AsyncMock()

    with patch(
        "app.services.activity_service.lead_repository.update_lead_pipeline", new=AsyncMock(return_value=None)
    ):
        with pytest.raises(LeadNotFoundError):
            await activity_service.change_lead_stage(mock_session, uuid.uuid4(), "won")


async def test_change_lead_stage_raises_service_unavailable_on_db_failure():
    mock_session = AsyncMock()

    with patch(
        "app.services.activity_service.lead_repository.update_lead_pipeline",
        new=AsyncMock(side_effect=ConnectionRefusedError("db unreachable")),
    ):
        with pytest.raises(LeadServiceUnavailableError):
            await activity_service.change_lead_stage(mock_session, uuid.uuid4(), "won")


async def test_create_activity_raises_not_found_when_lead_missing():
    mock_session = AsyncMock()

    with patch("app.services.activity_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await activity_service.create_activity(
                mock_session, uuid.uuid4(), type="email", description="Cold email generated"
            )


async def test_create_activity_returns_response_when_lead_exists():
    mock_session = AsyncMock()
    lead = _lead()
    fake_activity = Activity(
        id=1, lead_id=lead.id, type="email", description="Cold email generated",
        created_at=datetime.now(timezone.utc),
    )

    with patch(
        "app.services.activity_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ), patch(
        "app.services.activity_service.activity_repository.add_activity",
        new=AsyncMock(return_value=fake_activity),
    ):
        response = await activity_service.create_activity(
            mock_session, lead.id, type="email", description="Cold email generated"
        )

    assert response.description == "Cold email generated"
    assert response.type == "email"


async def test_list_activities_raises_not_found_when_lead_missing():
    mock_session = AsyncMock()

    with patch("app.services.activity_service.lead_repository.get_by_id", new=AsyncMock(return_value=None)):
        with pytest.raises(LeadNotFoundError):
            await activity_service.list_activities(mock_session, uuid.uuid4())


async def test_list_activities_returns_items_latest_first():
    mock_session = AsyncMock()
    lead = _lead()
    now = datetime.now(timezone.utc)
    fake_activities = [
        Activity(id=2, lead_id=lead.id, type="stage_change", description="Moved to Won", created_at=now),
        Activity(id=1, lead_id=lead.id, type="email", description="Cold email generated", created_at=now),
    ]

    with patch(
        "app.services.activity_service.lead_repository.get_by_id", new=AsyncMock(return_value=lead)
    ), patch(
        "app.services.activity_service.activity_repository.list_by_lead",
        new=AsyncMock(return_value=fake_activities),
    ):
        response = await activity_service.list_activities(mock_session, lead.id)

    assert len(response.items) == 2
    assert response.items[0].description == "Moved to Won"
