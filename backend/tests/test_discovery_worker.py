from unittest.mock import AsyncMock, patch

import httpx

from app.core.config import Settings
from app.workers.discovery_worker import _process_and_save_lead, compute_dedupe_key


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def _mock_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))


def test_compute_dedupe_key_is_deterministic():
    key1 = compute_dedupe_key("google_maps", "Joe's Plumbing", "+92 300 1234567", None, "Karachi")
    key2 = compute_dedupe_key("google_maps", "Joe's Plumbing", "+92 300 1234567", None, "Karachi")
    assert key1 == key2
    assert len(key1) == 64  # sha256 hex digest


def test_compute_dedupe_key_normalizes_whitespace_and_case():
    key1 = compute_dedupe_key("google_maps", "Joe's  Plumbing", "+92 300 1234567", None, None)
    key2 = compute_dedupe_key("google_maps", "joe's plumbing", "+92 300 1234567", None, None)
    assert key1 == key2


def test_compute_dedupe_key_differs_by_source():
    key1 = compute_dedupe_key("google_maps", "Joe's Plumbing", "+92 300 1234567", None, None)
    key2 = compute_dedupe_key("facebook", "Joe's Plumbing", "+92 300 1234567", None, None)
    assert key1 != key2


async def test_process_and_save_lead_without_website_skips_enrichment():
    lead = {
        "name": "  Joe's  Plumbing ",
        "location": "123 Main St, Karachi",
        "website": None,
        "phone": "0300 1234567",
        "source": "google_maps",
        "has_website": False,
        "raw_data": {"rating": 4.5, "category": "Plumber", "address": "123 Main St, Karachi"},
    }
    mock_session = AsyncMock()

    with (
        patch(
            "app.workers.discovery_worker.deduplicator_service.resolve_dedupe_key",
            new=AsyncMock(side_effect=lambda session, **kwargs: kwargs["computed_dedupe_key"]),
        ) as mock_resolve,
        patch("app.workers.discovery_worker.lead_repository.upsert_lead") as mock_upsert,
    ):
        mock_upsert.return_value = AsyncMock()
        await _process_and_save_lead(
            mock_session, _mock_http_client(), _settings(), lead, "plumbers", "Karachi"
        )

    mock_resolve.assert_awaited_once()
    mock_upsert.assert_awaited_once()
    saved = mock_upsert.call_args.args[1]

    assert saved["name"] == "Joe's Plumbing"  # normalized whitespace
    assert saved["phone"] == "+923001234567"  # normalized via phonenumbers
    assert saved["rating"] == 4.5
    assert saved["category"] == "Plumber"
    assert saved["query"] == "plumbers"
    assert saved["search_location"] == "Karachi"
    assert saved["website_score"] is None
    assert saved["website_domain"] is None
    assert saved["dedupe_key"] == compute_dedupe_key(
        "google_maps", "Joe's Plumbing", "+923001234567", None, "123 Main St, Karachi"
    )


async def test_process_and_save_lead_with_website_runs_enrichment():
    lead = {
        "name": "Bahu Plumbers",
        "location": "Karachi",
        "website": "https://bahuplumbers.org",
        "phone": None,
        "source": "google_maps",
        "has_website": True,
        "raw_data": {},
    }
    mock_session = AsyncMock()
    fake_enrichment = {
        "website_score": 82.5,
        "website_score_details": {"performance": 80.0, "seo": 90.0, "best_practices": 77.5},
        "emails": ["info@bahuplumbers.org"],
        "tech_stack": ["WordPress"],
        "is_registered": None,
        "logo_valid": True,
        "enriched_at": "2026-07-14T00:00:00+00:00",
    }

    with (
        patch(
            "app.workers.discovery_worker.deduplicator_service.resolve_dedupe_key",
            new=AsyncMock(side_effect=lambda session, **kwargs: kwargs["computed_dedupe_key"]),
        ),
        patch(
            "app.workers.discovery_worker.enrich_lead", new=AsyncMock(return_value=fake_enrichment)
        ) as mock_enrich,
        patch("app.workers.discovery_worker.lead_repository.upsert_lead") as mock_upsert,
    ):
        mock_upsert.return_value = AsyncMock()
        await _process_and_save_lead(
            mock_session, _mock_http_client(), _settings(), lead, "plumbers", "Karachi"
        )

    mock_enrich.assert_awaited_once()
    saved = mock_upsert.call_args.args[1]
    assert saved["website_score"] == 82.5
    assert saved["emails"] == ["info@bahuplumbers.org"]
    assert saved["tech_stack"] == ["WordPress"]
    assert saved["logo_valid"] is True
    assert saved["website_domain"] == "bahuplumbers.org"
