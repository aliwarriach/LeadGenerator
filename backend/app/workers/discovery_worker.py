import asyncio
import functools
import hashlib
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.models.discovery_job import DiscoveryEventType
from app.repositories import lead_repository
from app.scrapers.base_scraper import (
    CaptchaDetectedError,
    JobStoppedError,
    ScrapeEventType,
    ScraperConfig,
    ScraperError,
)
from app.scrapers.facebook_scraper import FacebookScraper
from app.scrapers.google_maps_scraper import GoogleMapsScraper
from app.scrapers.serper_worker import SerperConfig, SerperWorker
from app.schemas.errors import ErrorDetail
from app.services import deduplicator_service
from app.services.enrichment_service import enrich_lead
from app.services.job_tracking_service import JobTracker
from app.services.normalizer_service import normalize_lead
from app.workers import cooldown

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")

ScrapeFn = Callable[[str, str], Awaitable[list[dict[str, Any]]]]

# Google Maps and Facebook both drive a real Chromium session against Google
# properties; several such sessions running concurrently from one IP is a
# stronger bot signal than the same request volume spread out over time.
# Serper is a plain HTTP API call with no such risk, so it isn't gated by
# this lock. A single process-wide lock is sufficient because there is
# exactly one ARQ worker process (app/workers/supervisor.py) — every job
# shares this event loop.
_browser_scrape_lock = asyncio.Lock()

_SCRAPE_EVENT_TYPE_MAP: dict[ScrapeEventType, DiscoveryEventType] = {
    ScrapeEventType.SCRAPER_STARTED: DiscoveryEventType.SCRAPER_STARTED,
    ScrapeEventType.BUSINESS_PROCESSING: DiscoveryEventType.BUSINESS_PROCESSING,
    ScrapeEventType.RATE_LIMIT_DELAY: DiscoveryEventType.RATE_LIMIT_DELAY,
    ScrapeEventType.ERROR: DiscoveryEventType.ERROR,
    ScrapeEventType.WARNING: DiscoveryEventType.WARNING,
}


def _scraper_callbacks(tracker: JobTracker) -> dict[str, Any]:
    """Builds the on_event/on_check_stop callbacks a scraper is constructed
    with, bound to `tracker`. Keeps the scraper layer decoupled from
    JobTracker/DB code — it only ever sees these two plain callables."""

    async def on_event(event_type: ScrapeEventType, message: str, payload: dict[str, Any]) -> None:
        if event_type == ScrapeEventType.WARNING:
            # Also bumps the per-job failure counter that feeds the
            # run-level "high failure rate" warning (see job_tracking_service).
            await tracker.record_extraction_failure(message)
            return
        if event_type == ScrapeEventType.BUSINESS_PROCESSING:
            await tracker.update_progress(current_business_name=payload.get("business_name"))

        await tracker.record_event(
            _SCRAPE_EVENT_TYPE_MAP.get(event_type, DiscoveryEventType.WARNING), message, payload=payload or None
        )

    return {"on_event": on_event, "on_check_stop": tracker.should_stop}


def build_scraper_config(settings: Settings) -> ScraperConfig:
    return ScraperConfig(
        headless=settings.scraper_headless,
        max_results=settings.scraper_max_results,
        max_retries=settings.scraper_max_retries,
        action_delay_min=settings.scraper_action_delay_min,
        action_delay_max=settings.scraper_action_delay_max,
        rate_limit_min=settings.scraper_rate_limit_min,
        rate_limit_max=settings.scraper_rate_limit_max,
        search_delay_min=settings.scraper_search_delay_min,
        search_delay_max=settings.scraper_search_delay_max,
        navigation_timeout_ms=settings.scraper_navigation_timeout_ms,
        locale=settings.scraper_locale,
        timezone_id=settings.scraper_timezone,
        geolocation={
            "latitude": settings.scraper_geolocation_lat,
            "longitude": settings.scraper_geolocation_lon,
        },
        viewport={
            "width": settings.scraper_viewport_width,
            "height": settings.scraper_viewport_height,
        },
        proxy_server=settings.scraper_proxy_server,
        proxy_username=settings.scraper_proxy_username,
        proxy_password=settings.scraper_proxy_password,
        user_agents=list(settings.scraper_user_agents),
        screenshot_dir=settings.scraper_screenshot_dir,
        profile_dir=settings.scraper_profile_dir,
    )


def build_serper_config(settings: Settings) -> SerperConfig:
    return SerperConfig(
        api_key=settings.serper_api_key,
        base_url=settings.serper_base_url,
        max_results=settings.serper_max_results,
        timeout_seconds=settings.serper_timeout_seconds,
        max_retries=settings.serper_max_retries,
        country=settings.serper_country,
        language=settings.serper_language,
    )


def compute_dedupe_key(
    source: str, name: str, phone: str | None, website: str | None, location: str | None
) -> str:
    """Hash (source, normalized name, best available secondary signal).

    Source-specific by design — this only catches a re-run of the *same*
    source/query landing on the same business again. Cross-source matches
    (e.g. Google Maps and Facebook finding the same business) are handled
    separately by deduplicator_service's fuzzy-name pass.
    """
    name_norm = _WHITESPACE_RE.sub(" ", name.strip().lower())
    secondary = (phone or website or location or "").strip().lower()
    secondary_norm = _WHITESPACE_RE.sub(" ", secondary)
    raw = f"{source}|{name_norm}|{secondary_norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _process_and_save_lead(
    session: AsyncSession,
    http_client: httpx.AsyncClient,
    settings: Settings,
    raw_lead: dict[str, Any],
    query: str,
    location: str,
) -> None:
    """Normalize -> deduplicate -> enrich (if website) -> upsert a single lead.

    Enrichment only runs (and `website_score` only gets computed) for leads
    with a website; leads without one skip straight to saving with every
    enrichment field set to None. This is a per-lead *website* quality
    signal, not the overall client rating — that's a separate mechanic
    built later.
    """
    normalized = normalize_lead(raw_lead, default_phone_region=settings.default_phone_region)

    computed_dedupe_key = compute_dedupe_key(
        normalized["source"],
        normalized["name"],
        normalized.get("phone"),
        normalized.get("website"),
        normalized.get("location"),
    )
    dedupe_key = await deduplicator_service.resolve_dedupe_key(
        session,
        computed_dedupe_key=computed_dedupe_key,
        name=normalized["name"],
        search_location=location,
        threshold=settings.fuzzy_match_name_threshold,
    )

    enrichment = await enrich_lead(http_client, normalized, settings)

    raw_data = normalized.get("raw_data", {})
    lead_data = {
        "name": normalized["name"],
        "location": normalized.get("location"),
        "website": normalized.get("website"),
        "website_domain": normalized.get("website_domain"),
        "phone": normalized.get("phone"),
        "source": normalized["source"],
        "has_website": normalized["has_website"],
        "rating": raw_data.get("rating"),
        "category": raw_data.get("category"),
        "query": query,
        "search_location": location,
        "dedupe_key": dedupe_key,
        "raw_data": raw_data,
        **enrichment,
    }
    await lead_repository.upsert_lead(session, lead_data)


async def _run_scrape_job(
    source: str,
    scrape_fn: ScrapeFn,
    query: str,
    location: str,
    settings: Settings,
    tracker: JobTracker,
    *,
    lock: asyncio.Lock | None = None,
) -> dict[str, Any]:
    """Scrape, then sequentially normalize -> dedupe -> enrich -> save each lead.

    Leads are processed sequentially (not gathered concurrently): a single
    AsyncSession isn't safe to share across concurrent awaits, and most
    enrichment APIs' free tiers can't absorb bursty concurrent traffic
    anyway — sequential processing doubles as informal rate limiting. It
    also means this is the loop where a cooperative stop request is checked
    and honored (the slow part — PageSpeed enrichment alone can take
    40-60s/lead — happens here, not inside the scraper itself).
    """
    logger.info("%s job started: query=%r location=%r", source, query, location)
    if lock is not None:
        async with lock:
            leads = await scrape_fn(query, location)
    else:
        leads = await scrape_fn(query, location)

    await tracker.update_progress(leads_found_delta=len(leads))

    saved = 0
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        async with async_session_factory() as session:
            for raw_lead in leads:
                if await tracker.should_stop():
                    await tracker.mark_stopped(
                        message=f"{source} scraper stopped by user request ({saved}/{len(leads)} leads saved)"
                    )
                    logger.warning("%s job stopped by user request: saved=%d/%d", source, saved, len(leads))
                    return {"source": source, "saved": saved}

                await _process_and_save_lead(session, http_client, settings, raw_lead, query, location)
                saved += 1
                lead_name = raw_lead.get("name", "unknown")
                await tracker.update_progress(current_business_name=lead_name, leads_saved_delta=1)
                await tracker.record_event(DiscoveryEventType.LEAD_SAVED, f'Added new lead "{lead_name}"')

    logger.info("%s job finished: scraped=%d saved=%d", source, len(leads), saved)
    await tracker.mark_completed(message=f"{source} scraper finished: {saved} leads saved")
    return {"source": source, "saved": saved}


async def _run_browser_scrape_job(
    source: str,
    scrape_fn: ScrapeFn,
    query: str,
    location: str,
    settings: Settings,
    redis: ArqRedis,
    tracker: JobTracker,
) -> dict[str, Any]:
    """Cooldown-aware wrapper around `_run_scrape_job` for the two
    Playwright-based sources (google_maps, facebook).

    Skips the run entirely while `source` is still cooling down from a prior
    block, so a source that just got CAPTCHA'd doesn't immediately get
    hammered again by the next queued job. Records success/failure against
    that same cooldown state so a clean run resets the escalation.
    """
    remaining = await cooldown.seconds_remaining(redis, source)
    if remaining is not None:
        logger.warning("%s: in cooldown for %ds — skipping this job", source, remaining)
        await tracker.mark_skipped_cooldown(
            remaining, message=f"{source} scraper skipped — cooling down for {remaining}s"
        )
        return {"source": source, "saved": 0}

    try:
        result = await _run_scrape_job(
            source, scrape_fn, query, location, settings, tracker, lock=_browser_scrape_lock
        )
    except JobStoppedError as exc:
        # Detected inside the scraper's own loop (before _run_scrape_job's
        # lead loop was ever reached) — _run_scrape_job never got a chance
        # to mark this itself, so it's done here instead. Cooldown is
        # deliberately left untouched: a user-requested stop is not a
        # bot-detection signal either way.
        logger.warning("%s: stopped by user request during scrape (%s)", source, exc)
        await tracker.mark_stopped(message=f"{source} scraper stopped by user request")
        return {"source": source, "saved": 0}
    except CaptchaDetectedError as exc:
        # Checked before the generic ScraperError case (it's a subclass): a
        # confirmed CAPTCHA is a stronger block signal and starts the
        # cooldown escalation much higher than an ordinary search failure.
        cooldown_seconds = await cooldown.record_failure(
            redis, source, base_seconds=cooldown.CAPTCHA_BASE_COOLDOWN_SECONDS
        )
        logger.error("%s: CAPTCHA detected (%s) — entering cooldown for %ds", source, exc, cooldown_seconds)
        error = ErrorDetail(
            code="blocked_captcha", message=str(exc), retryable=True, retry_after_seconds=cooldown_seconds
        )
        await tracker.mark_blocked(
            error, message=f"CAPTCHA detected on {source} — cooling down for {cooldown_seconds}s"
        )
        return {"source": source, "saved": 0}
    except ScraperError as exc:
        cooldown_seconds = await cooldown.record_failure(redis, source)
        logger.error(
            "%s: scrape failed (%s) — entering cooldown for %ds", source, exc, cooldown_seconds
        )
        error = ErrorDetail(
            code="blocked_other", message=str(exc), retryable=True, retry_after_seconds=cooldown_seconds
        )
        await tracker.mark_blocked(error, message=f"{source} scraper failed: {exc}")
        return {"source": source, "saved": 0}

    await cooldown.record_success(redis, source)
    return result


async def _run_job_with_safety_net(
    tracker: JobTracker, job_id: str, source: str, coro: Awaitable[dict[str, Any]]
) -> dict[str, Any]:
    """Guarantees the DiscoveryJob row reaches a terminal state even if a
    genuinely unexpected exception (a bug, not a classified scrape failure)
    escapes the normal handling above — otherwise the row would stay stuck
    at "running" forever. Re-raises so ARQ's own retry/failure semantics
    still apply on top."""
    try:
        return await coro
    except Exception as exc:
        logger.exception("%s job %s crashed unexpectedly", source, job_id)
        await tracker.mark_failed(
            ErrorDetail(code="blocked_other", message=str(exc), retryable=True),
            message=f"{source} scraper crashed: {exc}",
        )
        raise


async def scrape_google_maps_job(
    ctx: dict, job_id: str, query: str, location: str, min_rating: float | None = None
) -> dict[str, Any]:
    settings = get_settings()
    tracker = JobTracker(uuid.UUID(job_id))
    await tracker.mark_running(message=f"Starting google_maps scraper for {query!r} in {location!r}")

    scraper = GoogleMapsScraper(build_scraper_config(settings), **_scraper_callbacks(tracker))
    # min_rating is Google-Maps-specific (Facebook/Serper results don't carry
    # a reliable rating) — bind it here rather than widening ScrapeFn's shape.
    scrape_fn = functools.partial(scraper.scrape, min_rating=min_rating)
    return await _run_job_with_safety_net(
        tracker,
        job_id,
        "google_maps",
        _run_browser_scrape_job("google_maps", scrape_fn, query, location, settings, ctx["redis"], tracker),
    )


async def scrape_facebook_job(
    ctx: dict, job_id: str, query: str, location: str, min_rating: float | None = None
) -> dict[str, Any]:
    settings = get_settings()
    tracker = JobTracker(uuid.UUID(job_id))
    await tracker.mark_running(message=f"Starting facebook scraper for {query!r} in {location!r}")

    scraper = FacebookScraper(build_scraper_config(settings), **_scraper_callbacks(tracker))
    return await _run_job_with_safety_net(
        tracker,
        job_id,
        "facebook",
        _run_browser_scrape_job("facebook", scraper.scrape, query, location, settings, ctx["redis"], tracker),
    )


async def scrape_serper_job(
    ctx: dict, job_id: str, query: str, location: str, min_rating: float | None = None
) -> dict[str, Any]:
    settings = get_settings()
    tracker = JobTracker(uuid.UUID(job_id))
    await tracker.mark_running(message=f"Starting serper search for {query!r} in {location!r}")

    worker = SerperWorker(build_serper_config(settings), on_event=_scraper_callbacks(tracker)["on_event"])
    return await _run_job_with_safety_net(
        tracker, job_id, "serper", _run_scrape_job("serper", worker.scrape, query, location, settings, tracker)
    )
