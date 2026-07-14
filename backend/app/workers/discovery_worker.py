import functools
import hashlib
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import async_session_factory
from app.repositories import lead_repository
from app.scrapers.base_scraper import ScraperConfig
from app.scrapers.facebook_scraper import FacebookScraper
from app.scrapers.google_maps_scraper import GoogleMapsScraper
from app.scrapers.serper_worker import SerperConfig, SerperWorker
from app.services import deduplicator_service
from app.services.enrichment_service import enrich_lead
from app.services.normalizer_service import normalize_lead

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")

ScrapeFn = Callable[[str, str], Awaitable[list[dict[str, Any]]]]


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
    source: str, scrape_fn: ScrapeFn, query: str, location: str, settings: Settings
) -> dict[str, Any]:
    logger.info("%s job started: query=%r location=%r", source, query, location)
    leads = await scrape_fn(query, location)

    # Leads are processed sequentially (not gathered concurrently): a single
    # AsyncSession isn't safe to share across concurrent awaits, and most
    # enrichment APIs' free tiers can't absorb bursty concurrent traffic
    # anyway — sequential processing doubles as informal rate limiting.
    saved = 0
    async with httpx.AsyncClient(
        timeout=settings.enrichment_client_timeout_seconds,
        headers={"User-Agent": settings.enrichment_user_agent},
    ) as http_client:
        async with async_session_factory() as session:
            for raw_lead in leads:
                await _process_and_save_lead(session, http_client, settings, raw_lead, query, location)
                saved += 1

    logger.info("%s job finished: scraped=%d saved=%d", source, len(leads), saved)
    return {
        "source": source,
        "query": query,
        "location": location,
        "scraped": len(leads),
        "saved": saved,
    }


async def scrape_google_maps_job(
    ctx: dict, query: str, location: str, min_rating: float | None = None
) -> dict[str, Any]:
    settings = get_settings()
    scraper = GoogleMapsScraper(build_scraper_config(settings))
    # min_rating is Google-Maps-specific (Facebook/Serper results don't carry
    # a reliable rating) — bind it here rather than widening ScrapeFn's shape.
    scrape_fn = functools.partial(scraper.scrape, min_rating=min_rating)
    return await _run_scrape_job("google_maps", scrape_fn, query, location, settings)


async def scrape_facebook_job(
    ctx: dict, query: str, location: str, min_rating: float | None = None
) -> dict[str, Any]:
    settings = get_settings()
    scraper = FacebookScraper(build_scraper_config(settings))
    return await _run_scrape_job("facebook", scraper.scrape, query, location, settings)


async def scrape_serper_job(
    ctx: dict, query: str, location: str, min_rating: float | None = None
) -> dict[str, Any]:
    settings = get_settings()
    worker = SerperWorker(build_serper_config(settings))
    return await _run_scrape_job("serper", worker.scrape, query, location, settings)
