import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.activity import Activity, ActivityType
from app.repositories import activity_repository


async def test_add_activity_commits_and_returns_activity():
    mock_session = AsyncMock()
    # AsyncSession.add() is synchronous in real SQLAlchemy — a bare AsyncMock
    # would make it awaitable and leave an unawaited-coroutine warning.
    mock_session.add = MagicMock()
    lead_id = uuid.uuid4()

    activity = await activity_repository.add_activity(
        mock_session, lead_id, type=ActivityType.EMAIL, description="Cold email generated"
    )

    assert activity.lead_id == lead_id
    assert activity.type == ActivityType.EMAIL
    assert activity.description == "Cold email generated"
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()
    mock_session.refresh.assert_awaited_once()


async def test_list_by_lead_returns_activities_latest_first():
    mock_session = AsyncMock()
    lead_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    fake_activities = [
        Activity(lead_id=lead_id, type="stage_change", description="Moved to Contacted", created_at=now),
        Activity(lead_id=lead_id, type="email", description="Cold email generated", created_at=now),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = fake_activities
    mock_session.execute = AsyncMock(return_value=result)

    activities = await activity_repository.list_by_lead(mock_session, lead_id)

    assert activities == fake_activities
