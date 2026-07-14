from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, TypeVar

from playwright.async_api import Browser, BrowserContext, Page, Playwright
from playwright_stealth import StealthConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")

_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


@dataclass
class ScraperConfig:
    """Framework-agnostic scraper settings.

    Built by the caller (worker layer) from app settings and passed in — scrapers
    never import FastAPI/DB code, so they stay independently testable/runnable.
    """

    headless: bool = False
    max_results: int = 50
    max_retries: int = 3

    action_delay_min: float = 0.5
    action_delay_max: float = 2.0
    rate_limit_min: float = 1.5
    rate_limit_max: float = 4.0
    search_delay_min: float = 4.0
    search_delay_max: float = 9.0
    navigation_timeout_ms: int = 30_000

    locale: str = "en-US"
    timezone_id: str = "Asia/Karachi"
    geolocation: dict[str, float] = field(
        default_factory=lambda: {"latitude": 24.8607, "longitude": 67.0011}
    )
    viewport: dict[str, int] = field(default_factory=lambda: {"width": 1920, "height": 1080})

    proxy_server: str | None = None
    proxy_username: str | None = None
    proxy_password: str | None = None

    user_agents: list[str] = field(default_factory=lambda: list(_DEFAULT_USER_AGENTS))

    screenshot_dir: str = "screenshots"

    @property
    def proxy(self) -> dict[str, str] | None:
        if not self.proxy_server:
            return None
        proxy: dict[str, str] = {"server": self.proxy_server}
        if self.proxy_username:
            proxy["username"] = self.proxy_username
        if self.proxy_password:
            proxy["password"] = self.proxy_password
        return proxy


class ScraperError(Exception):
    """Raised when a scrape run fails after exhausting retries."""


class BaseScraper(ABC):
    """Shared Playwright lifecycle, stealth setup, and human-behavior helpers.

    Subclasses implement `scrape()` for a specific source (Google Maps, Facebook)
    and call the protected helpers below for navigation/interaction.
    """

    source: str

    def __init__(self, config: ScraperConfig | None = None) -> None:
        self.config = config or ScraperConfig()

    # ---- lifecycle -----------------------------------------------------

    @asynccontextmanager
    async def browser_session(self, playwright: Playwright) -> AsyncIterator[BrowserContext]:
        browser = await self._launch_browser(playwright)
        context = await self.create_stealth_context(browser)
        try:
            yield context
        finally:
            await context.close()
            await browser.close()

    async def _launch_browser(self, playwright: Playwright) -> Browser:
        return await playwright.chromium.launch(
            headless=self.config.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )

    async def create_stealth_context(self, browser: Browser) -> BrowserContext:
        """Create a browser context with a realistic, randomized fingerprint."""
        user_agent = random.choice(self.config.user_agents)
        context = await browser.new_context(
            viewport=self.config.viewport,
            user_agent=user_agent,
            locale=self.config.locale,
            timezone_id=self.config.timezone_id,
            geolocation=self.config.geolocation,
            permissions=["geolocation"],
            proxy=self.config.proxy,
        )
        context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
        context.set_default_timeout(self.config.navigation_timeout_ms)
        return context

    async def new_stealth_page(self, context: BrowserContext) -> Page:
        page = await context.new_page()
        # playwright-stealth 1.0.6's stealth_async() applies each evasion script via
        # its own add_init_script() call, but navigator.userAgent.js reads a shared
        # `opts` const defined in a separate script — those don't share scope across
        # distinct CDP-injected scripts, so it throws at runtime. Combining all
        # evasion scripts into a single init script keeps `opts` in scope for all of
        # them, matching this library's own documented (but unimplemented) intent.
        combined_script = "\n".join(StealthConfig().enabled_scripts)
        await page.add_init_script(combined_script)
        return page

    # ---- human-like behavior --------------------------------------------

    async def human_delay(self, min_s: float | None = None, max_s: float | None = None) -> None:
        lo = self.config.action_delay_min if min_s is None else min_s
        hi = self.config.action_delay_max if max_s is None else max_s
        await asyncio.sleep(random.uniform(lo, hi))

    async def rate_limit_delay(self) -> None:
        await asyncio.sleep(random.uniform(self.config.rate_limit_min, self.config.rate_limit_max))

    async def search_delay(self) -> None:
        await asyncio.sleep(random.uniform(self.config.search_delay_min, self.config.search_delay_max))

    async def human_mouse_move(self, page: Page, target_x: float, target_y: float) -> None:
        """Move the mouse to a target point through a few randomized intermediate steps."""
        steps = random.randint(4, 9)
        await page.mouse.move(target_x, target_y, steps=steps)
        await asyncio.sleep(random.uniform(0.05, 0.2))

    async def human_click(self, page: Page, locator) -> None:
        """Move to an element with a natural path, then click at a randomized offset."""
        box = await locator.bounding_box()
        if box is None:
            await locator.click()
            return
        offset_x = box["width"] * random.uniform(0.3, 0.7)
        offset_y = box["height"] * random.uniform(0.3, 0.7)
        await self.human_mouse_move(page, box["x"] + offset_x, box["y"] + offset_y)
        await asyncio.sleep(random.uniform(0.05, 0.25))
        await locator.click()
        await self.human_delay(0.2, 0.6)

    async def human_scroll(
        self,
        page: Page,
        selector: str | None = None,
        total_steps: int = 6,
        direction: int = 1,
    ) -> None:
        """Scroll a container (or the page) in small, varied increments.

        If `selector` is given, scrolls that element's scrollTop (e.g. a results
        side panel); otherwise scrolls the window via mouse wheel.
        """
        for _ in range(total_steps):
            delta = random.randint(200, 500) * direction
            if selector:
                await page.evaluate(
                    "(args) => { const el = document.querySelector(args.sel); "
                    "if (el) el.scrollTop += args.delta; }",
                    {"sel": selector, "delta": delta},
                )
            else:
                await page.mouse.wheel(0, delta)
            await asyncio.sleep(random.uniform(0.3, 1.1))

    # ---- retry / error handling -----------------------------------------

    async def with_retry(
        self,
        func: Callable[[], Awaitable[T]],
        *,
        op_name: str,
        page: Page | None = None,
    ) -> T:
        """Run `func` with exponential backoff + jitter, up to `max_retries` attempts.

        Takes a screenshot (if `page` is given) and raises ScraperError once
        retries are exhausted.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return await func()
            except Exception as exc:  # noqa: BLE001 - broad by design, retried/logged
                last_exc = exc
                logger.warning(
                    "%s: attempt %s/%s failed: %s",
                    op_name,
                    attempt,
                    self.config.max_retries,
                    exc,
                )
                if attempt < self.config.max_retries:
                    backoff = (2 ** (attempt - 1)) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)

        logger.error("%s: exhausted %s retries", op_name, self.config.max_retries, exc_info=last_exc)
        if page is not None:
            await self.screenshot_on_failure(page, op_name)
        raise ScraperError(f"{op_name} failed after {self.config.max_retries} attempts") from last_exc

    async def screenshot_on_failure(self, page: Page, name: str) -> None:
        try:
            directory = Path(self.config.screenshot_dir)
            directory.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            safe_name = "".join(c if c.isalnum() else "_" for c in name)
            path = directory / f"{safe_name}_{timestamp}.png"
            await page.screenshot(path=str(path), full_page=True)
            logger.info("Saved failure screenshot to %s", path)
        except Exception as exc:  # noqa: BLE001 - screenshotting must never mask the real error
            logger.warning("Failed to capture failure screenshot: %s", exc)

    # ---- normalization ----------------------------------------------------

    def normalize(
        self,
        *,
        name: str,
        location: str | None,
        website: str | None,
        phone: str | None,
        raw_data: dict[str, Any],
    ) -> dict[str, Any]:
        website = website.strip() if website else None
        return {
            "name": name.strip(),
            "location": location.strip() if location else None,
            "website": website,
            "phone": phone.strip() if phone else None,
            "source": self.source,
            "has_website": bool(website),
            "raw_data": raw_data,
        }

    # ---- interface --------------------------------------------------------

    @abstractmethod
    async def scrape(self, query: str, location: str) -> list[dict[str, Any]]:
        """Run the scrape and return a list of normalized lead dicts."""
        raise NotImplementedError
