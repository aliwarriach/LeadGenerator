import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.models.discovery_job import DiscoveryEventType
from app.scrapers.base_scraper import CaptchaDetectedError, JobStoppedError, ScrapeEventType, ScraperError
from app.workers import cooldown
from app.workers.discovery_worker import (
    _browser_scrape_lock,
    _process_and_save_lead,
    _run_browser_scrape_job,
    _run_job_with_safety_net,
    _run_scrape_job,
    _scraper_callbacks,
    compute_dedupe_key,
    scrape_facebook_job,
    scrape_google_maps_job,
    scrape_serper_job,
)


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


def _mock_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)))


def _tracker(**overrides) -> AsyncMock:
    tracker = AsyncMock()
    tracker.should_stop = AsyncMock(return_value=overrides.get("should_stop", False))
    return tracker


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


async def test_run_scrape_job_serializes_calls_sharing_a_lock():
    lock = asyncio.Lock()
    events: list[str] = []

    async def scrape_fn(query: str, location: str) -> list:
        events.append(f"start:{location}")
        await asyncio.sleep(0.05)
        events.append(f"end:{location}")
        return []

    await asyncio.gather(
        _run_scrape_job("google_maps", scrape_fn, "plumbers", "Karachi", _settings(), _tracker(), lock=lock),
        _run_scrape_job("facebook", scrape_fn, "plumbers", "Lahore", _settings(), _tracker(), lock=lock),
    )

    # One call's scrape must fully finish before the other's starts — no interleaving.
    assert events in (
        ["start:Karachi", "end:Karachi", "start:Lahore", "end:Lahore"],
        ["start:Lahore", "end:Lahore", "start:Karachi", "end:Karachi"],
    )


async def test_run_scrape_job_without_lock_runs_concurrently():
    events: list[str] = []

    async def scrape_fn(query: str, location: str) -> list:
        events.append(f"start:{location}")
        await asyncio.sleep(0.05)
        events.append(f"end:{location}")
        return []

    await asyncio.gather(
        _run_scrape_job("serper", scrape_fn, "plumbers", "Karachi", _settings(), _tracker()),
        _run_scrape_job("serper", scrape_fn, "plumbers", "Lahore", _settings(), _tracker()),
    )

    # Unlocked: both scrapes start before either finishes.
    assert events[0].startswith("start:")
    assert events[1].startswith("start:")


async def test_run_scrape_job_marks_completed_on_clean_finish():
    tracker = _tracker()

    async def scrape_fn(query: str, location: str) -> list:
        return []

    result = await _run_scrape_job("serper", scrape_fn, "plumbers", "Karachi", _settings(), tracker)

    assert result == {"source": "serper", "saved": 0}
    tracker.mark_completed.assert_awaited_once()
    tracker.mark_stopped.assert_not_awaited()


async def test_run_scrape_job_honors_stop_mid_loop_and_keeps_partial_progress():
    tracker = _tracker()
    tracker.should_stop = AsyncMock(side_effect=[False, True])

    leads = [
        {
            "name": "A",
            "location": "Karachi",
            "website": None,
            "phone": None,
            "source": "google_maps",
            "has_website": False,
            "raw_data": {},
        },
        {
            "name": "B",
            "location": "Karachi",
            "website": None,
            "phone": None,
            "source": "google_maps",
            "has_website": False,
            "raw_data": {},
        },
    ]

    async def scrape_fn(query: str, location: str) -> list:
        return leads

    with (
        patch(
            "app.workers.discovery_worker.deduplicator_service.resolve_dedupe_key",
            new=AsyncMock(side_effect=lambda session, **kwargs: kwargs["computed_dedupe_key"]),
        ),
        patch("app.workers.discovery_worker.lead_repository.upsert_lead", new=AsyncMock()) as mock_upsert,
    ):
        result = await _run_scrape_job("google_maps", scrape_fn, "plumbers", "Karachi", _settings(), tracker)

    # Stopped after the first lead was saved — partial progress preserved, second skipped.
    assert result == {"source": "google_maps", "saved": 1}
    mock_upsert.assert_awaited_once()
    tracker.mark_stopped.assert_awaited_once()
    tracker.mark_completed.assert_not_awaited()


async def test_scrape_google_maps_job_uses_shared_browser_lock():
    fake_tracker = AsyncMock()
    with (
        patch("app.workers.discovery_worker.JobTracker", return_value=fake_tracker),
        patch("app.workers.discovery_worker.GoogleMapsScraper"),
        patch("app.workers.discovery_worker.cooldown.seconds_remaining", new=AsyncMock(return_value=None)),
        patch("app.workers.discovery_worker.cooldown.record_success", new=AsyncMock()),
        patch(
            "app.workers.discovery_worker._run_scrape_job",
            new=AsyncMock(return_value={"source": "google_maps", "saved": 0}),
        ) as mock_run,
    ):
        await scrape_google_maps_job({"redis": AsyncMock()}, str(uuid.uuid4()), "plumbers", "Karachi")

    assert mock_run.call_args.kwargs["lock"] is _browser_scrape_lock
    fake_tracker.mark_running.assert_awaited_once()


async def test_scrape_facebook_job_uses_shared_browser_lock():
    fake_tracker = AsyncMock()
    with (
        patch("app.workers.discovery_worker.JobTracker", return_value=fake_tracker),
        patch("app.workers.discovery_worker.FacebookScraper"),
        patch("app.workers.discovery_worker.cooldown.seconds_remaining", new=AsyncMock(return_value=None)),
        patch("app.workers.discovery_worker.cooldown.record_success", new=AsyncMock()),
        patch(
            "app.workers.discovery_worker._run_scrape_job",
            new=AsyncMock(return_value={"source": "facebook", "saved": 0}),
        ) as mock_run,
    ):
        await scrape_facebook_job({"redis": AsyncMock()}, str(uuid.uuid4()), "plumbers", "Karachi")

    assert mock_run.call_args.kwargs["lock"] is _browser_scrape_lock
    fake_tracker.mark_running.assert_awaited_once()


async def test_scrape_serper_job_does_not_share_the_browser_lock():
    fake_tracker = AsyncMock()
    with (
        patch("app.workers.discovery_worker.JobTracker", return_value=fake_tracker),
        patch("app.workers.discovery_worker.SerperWorker"),
        patch(
            "app.workers.discovery_worker._run_scrape_job",
            new=AsyncMock(return_value={"source": "serper", "saved": 0}),
        ) as mock_run,
    ):
        await scrape_serper_job({}, str(uuid.uuid4()), "plumbers", "Karachi")

    assert "lock" not in mock_run.call_args.kwargs


async def test_run_browser_scrape_job_skips_when_in_cooldown():
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=120)
    tracker = _tracker()

    async def scrape_fn(query: str, location: str) -> list:
        raise AssertionError("scrape_fn must not run while the source is cooling down")

    result = await _run_browser_scrape_job(
        "google_maps", scrape_fn, "plumbers", "Karachi", _settings(), redis, tracker
    )

    assert result == {"source": "google_maps", "saved": 0}
    tracker.mark_skipped_cooldown.assert_awaited_once()
    assert tracker.mark_skipped_cooldown.call_args.args[0] == 120


async def test_run_browser_scrape_job_records_failure_on_scraper_error():
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    redis.incr = AsyncMock(return_value=1)
    tracker = _tracker()

    async def scrape_fn(query: str, location: str) -> list:
        raise ScraperError("search timed out")

    result = await _run_browser_scrape_job(
        "google_maps", scrape_fn, "plumbers", "Karachi", _settings(), redis, tracker
    )

    assert result == {"source": "google_maps", "saved": 0}
    tracker.mark_blocked.assert_awaited_once()
    error = tracker.mark_blocked.call_args.args[0]
    assert error.code == "blocked_other"
    assert error.retry_after_seconds == cooldown.BASE_COOLDOWN_SECONDS
    redis.set.assert_awaited_once_with(
        "scraper:cooldown:google_maps", 1, ex=cooldown.BASE_COOLDOWN_SECONDS
    )


async def test_run_browser_scrape_job_uses_harsher_cooldown_tier_for_captcha():
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    redis.incr = AsyncMock(return_value=1)
    tracker = _tracker()

    async def scrape_fn(query: str, location: str) -> list:
        raise CaptchaDetectedError("CAPTCHA interstitial URL: https://www.google.com/sorry/index")

    result = await _run_browser_scrape_job(
        "google_maps", scrape_fn, "plumbers", "Karachi", _settings(), redis, tracker
    )

    assert result == {"source": "google_maps", "saved": 0}
    tracker.mark_blocked.assert_awaited_once()
    error = tracker.mark_blocked.call_args.args[0]
    assert error.code == "blocked_captcha"
    assert error.retry_after_seconds == cooldown.CAPTCHA_BASE_COOLDOWN_SECONDS
    redis.set.assert_awaited_once_with(
        "scraper:cooldown:google_maps", 1, ex=cooldown.CAPTCHA_BASE_COOLDOWN_SECONDS
    )


async def test_run_browser_scrape_job_marks_stopped_without_cooldown_on_job_stopped_error():
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    tracker = _tracker()

    async def scrape_fn(query: str, location: str) -> list:
        raise JobStoppedError("stopped mid-scrape")

    result = await _run_browser_scrape_job(
        "google_maps", scrape_fn, "plumbers", "Karachi", _settings(), redis, tracker
    )

    assert result == {"source": "google_maps", "saved": 0}
    tracker.mark_stopped.assert_awaited_once()
    redis.set.assert_not_awaited()
    redis.delete.assert_not_awaited()


async def test_run_browser_scrape_job_records_success_on_clean_run():
    redis = AsyncMock()
    redis.ttl = AsyncMock(return_value=-2)
    tracker = _tracker()

    async def scrape_fn(query: str, location: str) -> list:
        return []

    result = await _run_browser_scrape_job(
        "google_maps", scrape_fn, "plumbers", "Karachi", _settings(), redis, tracker
    )

    assert result == {"source": "google_maps", "saved": 0}
    redis.delete.assert_awaited_once_with("scraper:strikes:google_maps")
    tracker.mark_completed.assert_awaited_once()


async def test_run_job_with_safety_net_marks_failed_and_reraises_unexpected_errors():
    tracker = AsyncMock()

    async def _boom():
        raise RuntimeError("unexpected bug")

    with pytest.raises(RuntimeError):
        await _run_job_with_safety_net(tracker, "job-1", "google_maps", _boom())

    tracker.mark_failed.assert_awaited_once()
    assert tracker.mark_failed.call_args.args[0].code == "blocked_other"


async def test_run_job_with_safety_net_passes_through_on_success():
    tracker = AsyncMock()

    async def _ok():
        return {"source": "google_maps", "saved": 3}

    result = await _run_job_with_safety_net(tracker, "job-1", "google_maps", _ok())

    assert result == {"source": "google_maps", "saved": 3}
    tracker.mark_failed.assert_not_awaited()


async def test_scraper_callbacks_warning_bumps_extraction_failure_counter():
    tracker = AsyncMock()
    callbacks = _scraper_callbacks(tracker)

    await callbacks["on_event"](ScrapeEventType.WARNING, "extraction failed", {})

    tracker.record_extraction_failure.assert_awaited_once_with("extraction failed")
    tracker.record_event.assert_not_awaited()


async def test_scraper_callbacks_business_processing_updates_current_business_and_records_event():
    tracker = AsyncMock()
    callbacks = _scraper_callbacks(tracker)

    await callbacks["on_event"](
        ScrapeEventType.BUSINESS_PROCESSING, 'Scraping business "X"', {"business_name": "X"}
    )

    tracker.update_progress.assert_awaited_once_with(current_business_name="X")
    tracker.record_event.assert_awaited_once()
    assert tracker.record_event.call_args.args[0] == DiscoveryEventType.BUSINESS_PROCESSING


async def test_scraper_callbacks_maps_other_event_types_and_forwards_payload():
    tracker = AsyncMock()
    callbacks = _scraper_callbacks(tracker)

    await callbacks["on_event"](ScrapeEventType.RATE_LIMIT_DELAY, "Rate limit delay (2.0s)", {"seconds": 2.0})

    tracker.record_event.assert_awaited_once_with(
        DiscoveryEventType.RATE_LIMIT_DELAY, "Rate limit delay (2.0s)", payload={"seconds": 2.0}
    )


async def test_scraper_callbacks_on_check_stop_is_tracker_should_stop():
    tracker = AsyncMock()
    callbacks = _scraper_callbacks(tracker)

    assert callbacks["on_check_stop"] is tracker.should_stop


async def test_run_scrape_job_emits_lead_saved_event_per_saved_lead():
    tracker = _tracker()
    lead = {
        "name": "A",
        "location": "Karachi",
        "website": None,
        "phone": None,
        "source": "google_maps",
        "has_website": False,
        "raw_data": {},
    }

    async def scrape_fn(query: str, location: str) -> list:
        return [lead]

    with (
        patch(
            "app.workers.discovery_worker.deduplicator_service.resolve_dedupe_key",
            new=AsyncMock(side_effect=lambda session, **kwargs: kwargs["computed_dedupe_key"]),
        ),
        patch("app.workers.discovery_worker.lead_repository.upsert_lead", new=AsyncMock()),
    ):
        await _run_scrape_job("google_maps", scrape_fn, "plumbers", "Karachi", _settings(), tracker)

    tracker.record_event.assert_any_call(DiscoveryEventType.LEAD_SAVED, 'Added new lead "A"')
