from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import quote_plus

from playwright.async_api import Page, async_playwright

from app.scrapers.base_scraper import BaseScraper, ScraperConfig, ScraperError

logger = logging.getLogger(__name__)

FEED_SELECTOR = 'div[role="feed"]'
LISTING_SELECTOR = 'div[role="feed"] div[role="article"]'
BACK_BUTTON_SELECTOR = 'button[aria-label="Back"]'
CONSENT_BUTTON_SELECTOR = 'button:has-text("Accept all")'

# Google Maps scroll-loads more results in batches; give up after this many
# consecutive scrolls that don't grow the listing count.
MAX_STALE_SCROLLS = 4
MAX_SCROLL_ATTEMPTS = 25


class GoogleMapsScraper(BaseScraper):
    source = "google_maps"

    def __init__(self, config: ScraperConfig | None = None) -> None:
        super().__init__(config)

    async def scrape(
        self, query: str, location: str, min_rating: float | None = None
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        async with async_playwright() as playwright:
            async with self.browser_session(playwright) as context:
                page = await self.new_stealth_page(context)
                try:
                    await self.with_retry(
                        lambda: self._search(page, query, location),
                        op_name=f"google_maps_search:{query}:{location}",
                        page=page,
                    )
                except ScraperError:
                    logger.error("Google Maps search failed for %r in %r", query, location)
                    return results

                results = await self._collect_results(page, query, location, min_rating)
        return results

    async def _search(self, page: Page, query: str, location: str) -> None:
        url = f"https://www.google.com/maps/search/{quote_plus(query)}+in+{quote_plus(location)}"
        await page.goto(url, wait_until="domcontentloaded")
        await self._dismiss_consent_dialog(page)
        await self.human_delay(1.0, 2.0)

        try:
            await page.wait_for_selector(FEED_SELECTOR, timeout=self.config.navigation_timeout_ms)
        except Exception:
            # No results feed — either zero results or Google redirected straight
            # to a single exact-match place page. Caller checks for the latter.
            if "/maps/place/" not in page.url:
                raise

    async def _dismiss_consent_dialog(self, page: Page) -> None:
        try:
            button = page.locator(CONSENT_BUTTON_SELECTOR).first
            await button.wait_for(state="visible", timeout=2_000)
            await self.human_click(page, button)
        except Exception:
            pass  # dialog didn't appear — nothing to dismiss

    async def _collect_results(
        self, page: Page, query: str, location: str, min_rating: float | None = None
    ) -> list[dict[str, Any]]:
        if "/maps/place/" in page.url and await page.locator(FEED_SELECTOR).count() == 0:
            lead = await self._safe_extract_current_place(page)
            if lead and self._meets_rating_threshold(lead, min_rating):
                return [lead]
            return []

        await self._load_listings(page)

        results: list[dict[str, Any]] = []
        index = 0
        max_results = self.config.max_results

        while len(results) < max_results and index < max_results * 3:
            listings = page.locator(LISTING_SELECTOR)
            count = await listings.count()
            if index >= count:
                grew = await self._scroll_feed_once(page)
                if not grew:
                    break
                continue

            lead = await self._safe_extract_listing(page, listings.nth(index), query, location)
            if lead and self._meets_rating_threshold(lead, min_rating):
                results.append(lead)
            index += 1
            await self.rate_limit_delay()

        return results

    @staticmethod
    def _meets_rating_threshold(lead: dict[str, Any], min_rating: float | None) -> bool:
        if min_rating is None:
            return True
        rating = lead.get("raw_data", {}).get("rating")
        # A listing with no rating at all can't be confirmed to meet the
        # threshold, so it's excluded rather than assumed to pass.
        return rating is not None and rating >= min_rating

    async def _load_listings(self, page: Page) -> None:
        stale_scrolls = 0
        last_count = 0
        for _ in range(MAX_SCROLL_ATTEMPTS):
            listings = page.locator(LISTING_SELECTOR)
            count = await listings.count()
            if count >= self.config.max_results:
                break
            await self.human_scroll(page, selector=FEED_SELECTOR, total_steps=2)
            new_count = await listings.count()
            if new_count <= last_count:
                stale_scrolls += 1
                if stale_scrolls >= MAX_STALE_SCROLLS:
                    break
            else:
                stale_scrolls = 0
            last_count = new_count

    async def _scroll_feed_once(self, page: Page) -> bool:
        before = await page.locator(LISTING_SELECTOR).count()
        await self.human_scroll(page, selector=FEED_SELECTOR, total_steps=2)
        after = await page.locator(LISTING_SELECTOR).count()
        return after > before

    async def _safe_extract_listing(
        self, page: Page, listing_locator, query: str, location: str
    ) -> dict[str, Any] | None:
        try:
            return await self.with_retry(
                lambda: self._extract_listing(page, listing_locator, query, location),
                op_name=f"google_maps_extract:{query}",
                page=page,
            )
        except ScraperError:
            return None

    async def _extract_listing(
        self, page: Page, listing_locator, query: str, location: str
    ) -> dict[str, Any]:
        await self.human_click(page, listing_locator)
        # The results feed's own <h1> ("Results") is already in the DOM before the
        # click, so waiting for "any h1" resolves immediately without waiting for
        # the detail panel to render. Clicking a listing navigates the URL to
        # /maps/place/..., which is a reliable, DOM-structure-independent signal
        # that the detail panel has actually loaded.
        await page.wait_for_url(re.compile(r"/maps/place/"), timeout=self.config.navigation_timeout_ms)
        await self.human_delay()

        lead = await self._extract_place_details(page, query, location)

        try:
            back_button = page.locator(BACK_BUTTON_SELECTOR).first
            if await back_button.count() > 0:
                await self.human_click(page, back_button)
            else:
                await page.go_back()
            await page.wait_for_selector(FEED_SELECTOR, timeout=self.config.navigation_timeout_ms)
        except Exception as exc:
            logger.warning("Failed to return to results feed: %s", exc)

        return lead

    async def _safe_extract_current_place(self, page: Page) -> dict[str, Any] | None:
        try:
            return await self._extract_place_details(page, "", "")
        except Exception as exc:
            logger.warning("Failed to extract single-result place page: %s", exc)
            return None

    async def _extract_place_details(self, page: Page, query: str, location: str) -> dict[str, Any]:
        # The search-results panel's own "Results" <h1> stays in the DOM after a
        # listing's detail panel opens, so `.first` would grab that instead of the
        # place name — the detail panel's title heading is appended after it.
        name = await self._text_or_none(page.locator("h1").last)
        if not name:
            raise ScraperError("Listing has no name — skipping")

        website = await self._attr_or_none(page.locator('a[data-item-id="authority"]').first, "href")
        address = await self._text_or_none(page.locator('button[data-item-id="address"]').first)
        phone = await self._extract_phone(page)
        rating = await self._extract_rating(page)

        raw_data: dict[str, Any] = {
            "query": query,
            "search_location": location,
            "address": address,
            "rating": rating,
            "maps_url": page.url,
        }

        return self.normalize(
            name=name,
            location=address or location,
            website=website,
            phone=phone,
            raw_data=raw_data,
        )

    async def _extract_phone(self, page: Page) -> str | None:
        button = page.locator('button[data-item-id^="phone:tel:"]').first
        if await button.count() == 0:
            return None
        item_id = await button.get_attribute("data-item-id")
        if item_id and "tel:" in item_id:
            return item_id.split("tel:", 1)[1].strip() or None
        return await self._text_or_none(button)

    async def _extract_rating(self, page: Page) -> float | None:
        # Google's rating class names are obfuscated and change without notice;
        # this is a best-effort extraction that degrades to None rather than failing.
        try:
            text = await page.locator("div.F7nice span[aria-hidden='true']").first.inner_text(
                timeout=2_000
            )
            return float(text.replace(",", "."))
        except Exception:
            return None

    @staticmethod
    async def _text_or_none(locator) -> str | None:
        try:
            if await locator.count() == 0:
                return None
            text = await locator.inner_text(timeout=2_000)
            return text.strip() or None
        except Exception:
            return None

    @staticmethod
    async def _attr_or_none(locator, attr: str) -> str | None:
        try:
            if await locator.count() == 0:
                return None
            value = await locator.get_attribute(attr, timeout=2_000)
            return value.strip() if value else None
        except Exception:
            return None
