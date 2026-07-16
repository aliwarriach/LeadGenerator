from __future__ import annotations

import asyncio
import logging
import random
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
import httpx

from app.scrapers.base_scraper import ScrapeEventType
from app.scrapers.domain_filters import is_business_domain

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")


@dataclass
class SerperConfig:
    api_key: str | None = None
    base_url: str = "https://google.serper.dev/search"
    max_results: int = 20
    timeout_seconds: float = 15.0
    max_retries: int = 3
    country: str = "pk"
    language: str = "en"


class SerperError(Exception):
    """Raised when the Serper API request fails after exhausting retries."""


class SerperWorker:
    """Discovers businesses via Serper.dev's Google organic-search API.

    Not a browser-based scraper (no Playwright), but implements the same
    `scrape(query, location) -> list[dict]` contract as GoogleMapsScraper /
    FacebookScraper so it can be dropped into the same pipeline.
    """

    source = "serper"

    def __init__(
        self,
        config: SerperConfig | None = None,
        http_client: httpx.AsyncClient | None = None,
        *,
        on_event: Callable[[ScrapeEventType, str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self.config = config or SerperConfig()
        self._http_client = http_client
        self._on_event = on_event

    async def _emit(self, event_type: ScrapeEventType, message: str, **payload: Any) -> None:
        if self._on_event is None:
            return
        try:
            await self._on_event(event_type, message, payload)
        except Exception as exc:  # noqa: BLE001 - reporting must never break the scrape
            logger.warning("Failed to emit scrape event %r: %s", event_type, exc)

    async def scrape(self, query: str, location: str) -> list[dict[str, Any]]:
        await self._emit(ScrapeEventType.SCRAPER_STARTED, f"Starting serper search for {query!r} in {location!r}")

        if not self.config.api_key:
            logger.warning("SERPER_API_KEY not configured — skipping serper source")
            return []

        if self._http_client is not None:
            return await self._scrape_with_client(self._http_client, query, location)

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            return await self._scrape_with_client(client, query, location)

    async def _scrape_with_client(
        self, client: httpx.AsyncClient, query: str, location: str
    ) -> list[dict[str, Any]]:
        payload = {
            "q": f"{query} in {location}",
            "num": self.config.max_results,
            "gl": self.config.country,
            "hl": self.config.language,
        }
        data = await self._request_with_retry(client, payload)
        if data is None:
            return []

        results: list[dict[str, Any]] = []
        for item in data.get("organic", [])[: self.config.max_results]:
            lead = self._normalize_result(item, query, location)
            if lead:
                results.append(lead)
        return results

    async def _request_with_retry(
        self, client: httpx.AsyncClient, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        headers = {"X-API-KEY": self.config.api_key, "Content-Type": "application/json"}
        last_exc: Exception | None = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = await client.post(self.config.base_url, json=payload, headers=headers)
                if response.status_code == 429:
                    raise SerperError(f"Rate limited (429): {response.text[:200]}")
                response.raise_for_status()
                return response.json()
            except Exception as exc:  # noqa: BLE001 - broad by design, retried/logged
                last_exc = exc
                logger.warning(
                    "serper_search: attempt %s/%s failed: %s", attempt, self.config.max_retries, exc
                )
                if attempt < self.config.max_retries:
                    backoff = (2 ** (attempt - 1)) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)

        logger.error("serper_search: exhausted %s retries", self.config.max_retries, exc_info=last_exc)
        return None

    def _normalize_result(self, item: dict[str, Any], query: str, location: str) -> dict[str, Any] | None:
        name = (item.get("title") or "").strip()
        if not name:
            return None

        link = item.get("link")
        website = link if is_business_domain(link) else None
        snippet = item.get("snippet")
        phone = self._extract_phone(snippet or "")

        raw_data = {
            "query": query,
            "search_location": location,
            "snippet": snippet,
            "position": item.get("position"),
            "serper_link": link,
        }
        return {
            "name": name,
            "location": location,
            "website": website,
            "phone": phone,
            "source": self.source,
            "has_website": bool(website),
            "raw_data": raw_data,
        }

    @staticmethod
    def _extract_phone(text: str) -> str | None:
        match = _PHONE_RE.search(text)
        return match.group(1).strip() if match else None
