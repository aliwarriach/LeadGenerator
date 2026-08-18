from __future__ import annotations

import logging
from typing import Any, TypedDict

import httpx
from bs4 import BeautifulSoup

from app.core.url_guard import safe_get

logger = logging.getLogger(__name__)

_HEADING_TAGS = ("h1", "h2")
_MAX_HEADINGS = 10


class WebsiteContent(TypedDict):
    title: str | None
    meta_description: str | None
    headings: list[str]
    text_sample: str


async def extract_content(
    client: httpx.AsyncClient,
    website: str,
    *,
    fetch_timeout_seconds: float,
    max_chars: int,
) -> WebsiteContent | None:
    """Fetch `website` and pull the signals a human reviewer would skim first:
    title, meta description, top headings, and a bounded text sample.

    This is the AI website audit's input, not a general-purpose scraper —
    it makes no attempt to render JS or crawl beyond the single page. Returns
    None on any fetch/parse failure, matching every other enricher's "never
    propagate" contract.
    """
    try:
        # safe_get, not client.get: `website` is untrusted scraped/user input
        # and this runs inside the VPC. See app/core/url_guard.py.
        response = await safe_get(client, website, timeout=fetch_timeout_seconds)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Website content fetch failed for %s: %s", website, exc)
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        title = soup.title.get_text(strip=True) if soup.title else None

        meta_description: str | None = None
        meta_tag = soup.find("meta", attrs={"name": "description"})
        if meta_tag and meta_tag.get("content"):
            meta_description = meta_tag["content"].strip() or None

        headings = [
            text
            for tag in soup.find_all(_HEADING_TAGS)
            if (text := tag.get_text(strip=True))
        ][:_MAX_HEADINGS]

        text_sample = soup.get_text(separator=" ", strip=True)[:max_chars]

        return WebsiteContent(
            title=title, meta_description=meta_description, headings=headings, text_sample=text_sample
        )
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Website content extraction failed for %s: %s", website, exc)
        return None
