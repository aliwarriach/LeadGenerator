from unittest.mock import AsyncMock, patch

import pytest

from app.services import dashboard_service
from app.services.lead_service import LeadServiceUnavailableError


async def test_get_stats_wraps_repository_error():
    with patch(
        "app.services.dashboard_service.dashboard_repository.get_stats",
        new=AsyncMock(side_effect=Exception("db down")),
    ):
        with pytest.raises(LeadServiceUnavailableError):
            await dashboard_service.get_stats(AsyncMock())


async def test_get_stats_returns_validated_response():
    fake_stats = {
        "discovered_total": 100,
        "discovered_this_week": 10,
        "no_website_total": 30,
        "no_website_pct": 30.0,
        "audits_completed_total": 40,
        "audits_completed_this_week": 5,
        "active_deals": 8,
    }
    with patch(
        "app.services.dashboard_service.dashboard_repository.get_stats",
        new=AsyncMock(return_value=fake_stats),
    ):
        result = await dashboard_service.get_stats(AsyncMock())

    assert result.discovered_total == 100
    assert result.active_deals == 8


async def test_get_discovery_volume_sums_total_across_days():
    fake_rows = [
        {"day": "2026-07-18", "has_website": 3, "no_website": 1},
        {"day": "2026-07-19", "has_website": 2, "no_website": 4},
    ]
    with patch(
        "app.services.dashboard_service.dashboard_repository.get_discovery_volume",
        new=AsyncMock(return_value=fake_rows),
    ):
        result = await dashboard_service.get_discovery_volume(AsyncMock(), days=2)

    assert result.total == 10
    assert len(result.days) == 2


async def test_get_lead_stage_mix_sums_total():
    fake_rows = [
        {"stage": "new_lead", "count": 10},
        {"stage": "contacted", "count": 5},
        {"stage": "qualified", "count": 0},
        {"stage": "proposal", "count": 0},
        {"stage": "won", "count": 2},
    ]
    with patch(
        "app.services.dashboard_service.dashboard_repository.get_lead_stage_mix",
        new=AsyncMock(return_value=fake_rows),
    ):
        result = await dashboard_service.get_lead_stage_mix(AsyncMock())

    assert result.total == 17
    assert len(result.items) == 5


async def test_list_recent_activity_wraps_repository_error():
    with patch(
        "app.services.dashboard_service.dashboard_repository.list_recent_activity",
        new=AsyncMock(side_effect=Exception("db down")),
    ):
        with pytest.raises(LeadServiceUnavailableError):
            await dashboard_service.list_recent_activity(AsyncMock(), limit=10)
