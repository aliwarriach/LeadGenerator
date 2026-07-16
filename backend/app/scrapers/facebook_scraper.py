from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, urlparse

from playwright.async_api import Page, async_playwright

from app.scrapers.base_scraper import BaseScraper, ScrapeEventType, ScraperConfig, ScraperError
from app.scrapers.domain_filters import is_business_domain

logger = logging.getLogger(__name__)

SEARCH_RESULTS_SELECTOR = "#search"
NEXT_PAGE_SELECTOR = "#pnnext"
CONSENT_BUTTON_SELECTOR = 'button:has-text("Accept all")'
MAX_SEARCH_PAGES = 3

_BLOCKED_PATH_SUBSTRINGS = (
    "/groups/",
    "/events/",
    "/watch",
    "/marketplace/",
    "/photo",
    "/videos/",
    "/posts/",
    "sharer",
    "/login",
    "/policies",
    "/help",
    "/plugins/",
    "l.facebook.com",
)

_PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
_CATEGORY_RE = re.compile(r"Page\s*[·•]\s*([^\n|]+)")
# Facebook's /about page renders phone numbers immediately before a "Mobile"
# or "Phone" field label (no tel: links, no nearby "call"/"phone" keyword) —
# e.g. "...Service area\n0321 4141862\nMobile\n...". This is a different
# layout from the homepage body, which is why it needs its own pattern.
_ABOUT_PHONE_RE = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)\s*\n\s*(?:Mobile|Phone)\b", re.IGNORECASE)


class FacebookScraper(BaseScraper):
    source = "facebook"

    async def scrape(self, query: str, location: str) -> list[dict[str, Any]]:
        await self._emit(ScrapeEventType.SCRAPER_STARTED, f"Starting facebook scraper for {query!r} in {location!r}")
        results: list[dict[str, Any]] = []
        async with async_playwright() as playwright:
            async with self.browser_session(playwright) as context:
                page = await self.new_stealth_page(context)

                try:
                    links = await self.with_retry(
                        lambda: self._search_google(page, query, location),
                        op_name=f"facebook_google_search:{query}:{location}",
                        page=page,
                    )
                except ScraperError:
                    # Re-raised rather than swallowed to an empty list: a failed
                    # search (timeout, CAPTCHA, layout change) is structurally
                    # different from "this niche genuinely has zero listings",
                    # and the caller needs that distinction to drive cooldown.
                    logger.error("Google search for Facebook pages failed for %r/%r", query, location)
                    raise

                for link in links[: self.config.max_results]:
                    await self._check_stop()
                    delay = await self.rate_limit_delay()
                    await self._emit(ScrapeEventType.RATE_LIMIT_DELAY, f"Rate limit delay ({delay:.1f}s)", seconds=delay)
                    lead = await self._safe_visit_page(page, link, query, location)
                    if lead:
                        results.append(lead)

        return results

    # ---- discovery via Google -------------------------------------------

    async def _search_google(self, page: Page, query: str, location: str) -> list[str]:
        search_query = f'site:facebook.com "{query}" "{location}"'
        url = f"https://www.google.com/search?q={quote_plus(search_query)}"
        await page.goto(url, wait_until="domcontentloaded")
        await self.detect_captcha(page)
        await self._dismiss_consent_dialog(page)
        await self.human_delay(1.0, 2.0)
        await page.wait_for_selector(SEARCH_RESULTS_SELECTOR, timeout=self.config.navigation_timeout_ms)

        links: list[str] = []
        seen: set[str] = set()

        for page_num in range(MAX_SEARCH_PAGES):
            await self.human_scroll(page, total_steps=3)
            anchors = page.locator(f'{SEARCH_RESULTS_SELECTOR} a[href*="facebook.com/"]')
            count = await anchors.count()
            for i in range(count):
                href = await anchors.nth(i).get_attribute("href")
                cleaned = self._clean_facebook_link(href)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    links.append(cleaned)

            if len(links) >= self.config.max_results:
                break

            next_button = page.locator(NEXT_PAGE_SELECTOR)
            if page_num < MAX_SEARCH_PAGES - 1 and await next_button.count() > 0:
                await self.search_delay()
                await self.human_click(page, next_button.first)
                await page.wait_for_selector(
                    SEARCH_RESULTS_SELECTOR, timeout=self.config.navigation_timeout_ms
                )
            else:
                break

        return links

    @staticmethod
    def _clean_facebook_link(href: str | None) -> str | None:
        if not href:
            return None
        if not any(domain in href for domain in ("facebook.com/", "fb.com/")):
            return None
        if any(blocked in href for blocked in _BLOCKED_PATH_SUBSTRINGS):
            return None
        parsed = urlparse(href)
        if not parsed.path or parsed.path == "/":
            return None
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    async def _dismiss_consent_dialog(self, page: Page) -> None:
        try:
            button = page.locator(CONSENT_BUTTON_SELECTOR).first
            await button.wait_for(state="visible", timeout=2_000)
            await self.human_click(page, button)
        except Exception:
            pass

    # ---- page visits -------------------------------------------------------

    async def _safe_visit_page(
        self, page: Page, url: str, query: str, location: str
    ) -> dict[str, Any] | None:
        try:
            return await self.with_retry(
                lambda: self._extract_page(page, url, query, location),
                op_name=f"facebook_extract:{url}",
                page=page,
            )
        except ScraperError as exc:
            await self._emit(ScrapeEventType.WARNING, f"Failed to extract a Facebook page: {exc}")
            return None

    async def _extract_page(self, page: Page, url: str, query: str, location: str) -> dict[str, Any]:
        await page.goto(url, wait_until="domcontentloaded")
        await self.human_delay(1.0, 2.0)
        await self.human_scroll(page, total_steps=3)

        name = await self._extract_name(page)
        if not name:
            raise ScraperError(f"No page name found at {url} — likely gated or removed")
        await self._emit(ScrapeEventType.BUSINESS_PROCESSING, f'Scraping business "{name}"', business_name=name)

        og_description = await self._meta_content(page, 'meta[property="og:description"]')
        body_text = await self._safe_inner_text(page, "body")

        category = await self._extract_category(page, body_text)
        website = await self._extract_website(page)
        phone = await self._extract_phone_from_about(page, url)
        if not phone:
            phone = self._extract_phone(body_text or og_description or "")

        raw_data: dict[str, Any] = {
            "query": query,
            "search_location": location,
            "facebook_url": url,
            "category": category,
            "og_description": og_description,
        }

        return self.normalize(
            name=name,
            location=location,
            website=website,
            phone=phone,
            raw_data=raw_data,
        )

    async def _extract_name(self, page: Page) -> str | None:
        try:
            text = await page.locator("h1").first.inner_text(timeout=3_000)
            if text and text.strip():
                return text.strip()
        except Exception:
            pass
        return await self._meta_content(page, 'meta[property="og:title"]')

    async def _extract_category(self, page: Page, body_text: str | None) -> str | None:
        try:
            locator = page.locator('a[href*="pages/category/"]').first
            if await locator.count() > 0:
                text = await locator.inner_text(timeout=2_000)
                if text and text.strip():
                    return text.strip()
        except Exception:
            pass
        if body_text:
            match = _CATEGORY_RE.search(body_text)
            if match:
                return match.group(1).strip()
        return None

    async def _extract_website(self, page: Page) -> str | None:
        # Facebook wraps outbound links through l.facebook.com/l.php?u=<real url>, so
        # that redirector must stay in the candidate set even though it's a
        # facebook.com host — but the unwrapped target still has to clear the
        # same is_business_domain check as everything else (Facebook proxies
        # links to a page's LinkedIn/Instagram/etc through here too).
        try:
            anchors = page.locator('a[href^="http"]')
            count = await anchors.count()
            for i in range(min(count, 30)):
                href = await anchors.nth(i).get_attribute("href")
                if not href:
                    continue
                if "l.facebook.com/l.php" in href:
                    parsed = urlparse(href)
                    target = parse_qs(parsed.query).get("u")
                    if target and is_business_domain(target[0]):
                        return target[0]
                    continue
                if not is_business_domain(href):
                    continue
                return href
        except Exception as exc:
            logger.debug("Website extraction failed: %s", exc)
        return None

    async def _extract_phone_from_about(self, page: Page, page_url: str) -> str | None:
        """Visit the page's /about subpage and pull the phone number from
        Facebook's contact-info field layout (number immediately followed by
        a "Mobile"/"Phone" label). Best-effort: any failure here just falls
        back to the homepage-body regex, it must never fail the whole lead.
        """
        about_url = page_url.rstrip("/") + "/about"
        try:
            await page.goto(about_url, wait_until="domcontentloaded")
            await self.human_delay(0.5, 1.2)
            body_text = await self._safe_inner_text(page, "body")
        except Exception as exc:
            logger.debug("Failed to load /about for phone extraction (%s): %s", page_url, exc)
            return None
        if not body_text:
            return None
        match = _ABOUT_PHONE_RE.search(body_text)
        return match.group(1).strip() if match else None

    @staticmethod
    def _extract_phone(text: str) -> str | None:
        keyword_idx = text.lower().find("call")
        if keyword_idx == -1:
            keyword_idx = text.lower().find("phone")
        window = text[max(0, keyword_idx - 20): keyword_idx + 60] if keyword_idx != -1 else text[:2000]
        match = _PHONE_RE.search(window)
        return match.group(1).strip() if match else None

    @staticmethod
    async def _meta_content(page: Page, selector: str) -> str | None:
        try:
            locator = page.locator(selector).first
            if await locator.count() == 0:
                return None
            content = await locator.get_attribute("content", timeout=2_000)
            return content.strip() if content else None
        except Exception:
            return None

    @staticmethod
    async def _safe_inner_text(page: Page, selector: str) -> str | None:
        try:
            return await page.locator(selector).first.inner_text(timeout=3_000)
        except Exception:
            return None
