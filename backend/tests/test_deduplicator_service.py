from unittest.mock import AsyncMock, patch

from app.models.lead import Lead
from app.services.deduplicator_service import _best_fuzzy_match, resolve_dedupe_key


def _lead(name: str, dedupe_key: str) -> Lead:
    return Lead(name=name, dedupe_key=dedupe_key)


async def test_resolve_dedupe_key_returns_computed_key_on_exact_match():
    mock_session = AsyncMock()
    with patch(
        "app.services.deduplicator_service.lead_repository.get_by_dedupe_key",
        new=AsyncMock(return_value=_lead("Bahu Plumbers", "abc123")),
    ):
        key = await resolve_dedupe_key(
            mock_session, computed_dedupe_key="abc123", name="Bahu Plumbers", search_location="Karachi"
        )
    assert key == "abc123"


async def test_resolve_dedupe_key_returns_computed_key_when_no_search_location():
    mock_session = AsyncMock()
    with patch(
        "app.services.deduplicator_service.lead_repository.get_by_dedupe_key",
        new=AsyncMock(return_value=None),
    ):
        key = await resolve_dedupe_key(
            mock_session, computed_dedupe_key="fresh-key", name="Bahu Plumbers", search_location=None
        )
    assert key == "fresh-key"


async def test_resolve_dedupe_key_reuses_fuzzy_matched_existing_key():
    existing = _lead("Bahu Plumbers LLC", "existing-key-456")
    mock_session = AsyncMock()
    with (
        patch(
            "app.services.deduplicator_service.lead_repository.get_by_dedupe_key",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.deduplicator_service.lead_repository.list_by_search_location",
            new=AsyncMock(return_value=[existing]),
        ),
    ):
        key = await resolve_dedupe_key(
            mock_session,
            computed_dedupe_key="fresh-key-from-facebook",
            name="Bahu Plumbers",
            search_location="Karachi",
        )
    assert key == "existing-key-456"


async def test_resolve_dedupe_key_falls_back_to_computed_key_when_no_close_match():
    unrelated = _lead("Totally Different Business", "unrelated-key")
    mock_session = AsyncMock()
    with (
        patch(
            "app.services.deduplicator_service.lead_repository.get_by_dedupe_key",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.services.deduplicator_service.lead_repository.list_by_search_location",
            new=AsyncMock(return_value=[unrelated]),
        ),
    ):
        key = await resolve_dedupe_key(
            mock_session,
            computed_dedupe_key="fresh-key",
            name="Bahu Plumbers",
            search_location="Karachi",
        )
    assert key == "fresh-key"


def test_best_fuzzy_match_returns_none_for_empty_candidates():
    assert _best_fuzzy_match("Bahu Plumbers", [], threshold=85.0) is None


def test_best_fuzzy_match_picks_highest_scoring_candidate_above_threshold():
    candidates = [
        _lead("Totally Unrelated Co", "k1"),
        _lead("Bahu Plumbers", "k2"),
        _lead("Bahu Plumbing Services", "k3"),
    ]
    match = _best_fuzzy_match("Bahu Plumbers", candidates, threshold=85.0)
    assert match is not None
    assert match.dedupe_key == "k2"
