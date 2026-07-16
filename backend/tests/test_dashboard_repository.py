from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from app.models.activity import Activity
from app.models.lead import Lead
from app.repositories import dashboard_repository


def _scalar_result(value):
    result = MagicMock()
    result.scalar_one.return_value = value
    return result


async def test_get_stats_computes_no_website_pct_and_zero_fills_safely():
    mock_session = AsyncMock()
    # order: discovered_total, discovered_this_week, no_website_total,
    # audits_completed_total, audits_completed_this_week, active_deals
    mock_session.execute = AsyncMock(
        side_effect=[
            _scalar_result(200),
            _scalar_result(20),
            _scalar_result(50),
            _scalar_result(80),
            _scalar_result(10),
            _scalar_result(14),
        ]
    )

    stats = await dashboard_repository.get_stats(mock_session, now=datetime(2026, 7, 20, tzinfo=timezone.utc))

    assert stats == {
        "discovered_total": 200,
        "discovered_this_week": 20,
        "no_website_total": 50,
        "no_website_pct": 25.0,
        "audits_completed_total": 80,
        "audits_completed_this_week": 10,
        "active_deals": 14,
    }


async def test_get_stats_no_website_pct_is_zero_when_no_leads():
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(
        side_effect=[
            _scalar_result(0),
            _scalar_result(0),
            _scalar_result(0),
            _scalar_result(0),
            _scalar_result(0),
            _scalar_result(0),
        ]
    )

    stats = await dashboard_repository.get_stats(mock_session)

    assert stats["no_website_pct"] == 0.0


async def test_get_discovery_volume_zero_fills_days_with_no_leads():
    mock_session = AsyncMock()
    result = MagicMock()
    # Only day 2 of a 3-day window has leads.
    result.all.return_value = [
        (date(2026, 7, 19), True, 5),
        (date(2026, 7, 19), False, 2),
    ]
    mock_session.execute = AsyncMock(return_value=result)

    rows = await dashboard_repository.get_discovery_volume(
        mock_session, days=3, now=datetime(2026, 7, 20, tzinfo=timezone.utc)
    )

    assert rows == [
        {"day": date(2026, 7, 18), "has_website": 0, "no_website": 0},
        {"day": date(2026, 7, 19), "has_website": 5, "no_website": 2},
        {"day": date(2026, 7, 20), "has_website": 0, "no_website": 0},
    ]


async def test_get_lead_stage_mix_zero_fills_stages_with_no_leads():
    mock_session = AsyncMock()
    result = MagicMock()
    result.all.return_value = [("new_lead", 10), ("won", 3)]
    mock_session.execute = AsyncMock(return_value=result)

    rows = await dashboard_repository.get_lead_stage_mix(mock_session)

    assert rows == [
        {"stage": "new_lead", "count": 10},
        {"stage": "contacted", "count": 0},
        {"stage": "qualified", "count": 0},
        {"stage": "proposal", "count": 0},
        {"stage": "won", "count": 3},
    ]


async def test_list_recent_activity_joins_lead_name():
    mock_session = AsyncMock()
    lead_id = "11111111-1111-1111-1111-111111111111"
    activity = Activity(id=1, lead_id=lead_id, type="stage_change", description="Moved to Qualified")
    activity.created_at = datetime(2026, 7, 20, tzinfo=timezone.utc)

    result = MagicMock()
    result.all.return_value = [(activity, "Al Noor Med Spa")]
    mock_session.execute = AsyncMock(return_value=result)

    rows = await dashboard_repository.list_recent_activity(mock_session, limit=10)

    assert rows == [
        {
            "id": 1,
            "lead_id": lead_id,
            "lead_name": "Al Noor Med Spa",
            "type": "stage_change",
            "description": "Moved to Qualified",
            "created_at": activity.created_at,
        }
    ]
