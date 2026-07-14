from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import Settings
from app.enrichers import (
    clearbit_enricher,
    hunter_enricher,
    opencorporates_enricher,
    pagespeed_enricher,
    wappalyzer_enricher,
)
from app.services.normalizer_service import normalize_domain

logger = logging.getLogger(__name__)

_EMPTY_ENRICHMENT: dict[str, Any] = {
    "website_score": None,
    "website_score_details": None,
    "emails": None,
    "tech_stack": None,
    "is_registered": None,
    "logo_valid": None,
    "enriched_at": None,
}


async def _none() -> None:
    return None


async def enrich_lead(client: httpx.AsyncClient, lead: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Enrich a normalized lead dict with website/company signals.

    Only computes `website_score` (and runs website-dependent enrichers) for
    leads that actually have a website — leads without one get every
    enrichment field set to None and `enriched_at` stays None since no
    enrichment pass ran at all. This is a distinct per-lead *website*
    quality signal, NOT an overall lead rating — that mechanic is separate
    and built later.

    Every individual enricher swallows its own errors and returns None on
    failure, so gathering them concurrently here is safe without
    `return_exceptions` — one flaky API never fails lead persistence.
    """
    website = lead.get("website")
    if not website:
        return dict(_EMPTY_ENRICHMENT)

    # Leads that already went through normalize_lead() carry a precomputed
    # website_domain; fall back to deriving it here so this still works
    # standalone (e.g. called directly in tests) without that prior step.
    domain = lead.get("website_domain") or normalize_domain(website)

    scores, emails, tech_stack, is_registered, logo_valid = await asyncio.gather(
        pagespeed_enricher.get_pagespeed_scores(
            client,
            website,
            api_key=settings.pagespeed_api_key,
            base_url=settings.pagespeed_base_url,
            strategy=settings.pagespeed_strategy,
            timeout_seconds=settings.pagespeed_timeout_seconds,
        ),
        hunter_enricher.find_emails(
            client,
            domain,
            api_key=settings.hunter_api_key,
            base_url=settings.hunter_base_url,
            timeout_seconds=settings.hunter_timeout_seconds,
            max_emails=settings.hunter_max_emails,
        ),
        wappalyzer_enricher.detect_tech_stack(
            client,
            website,
            fetch_timeout_seconds=settings.wappalyzer_fetch_timeout_seconds,
        )
        if settings.wappalyzer_enabled
        else _none(),
        opencorporates_enricher.validate_company(
            client,
            lead["name"],
            api_key=settings.opencorporates_api_key,
            base_url=settings.opencorporates_base_url,
            timeout_seconds=settings.opencorporates_timeout_seconds,
        ),
        clearbit_enricher.validate_logo(
            client,
            domain,
            base_url=settings.clearbit_logo_base_url,
            timeout_seconds=settings.clearbit_timeout_seconds,
        ),
    )

    return {
        "website_score": pagespeed_enricher.compute_website_quality_score(scores) if scores else None,
        "website_score_details": scores,
        "emails": emails,
        "tech_stack": tech_stack,
        "is_registered": is_registered,
        "logo_valid": logo_valid,
        "enriched_at": datetime.now(timezone.utc),
    }
