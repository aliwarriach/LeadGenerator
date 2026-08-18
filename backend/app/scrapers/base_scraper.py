from __future__ import annotations

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, TypeVar

from playwright.async_api import BrowserContext, Page, Playwright
from playwright_stealth import StealthConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ScrapeEventType(StrEnum):
    SCRAPER_STARTED = "scraper_started"
    BUSINESS_PROCESSING = "business_processing"
    RATE_LIMIT_DELAY = "rate_limit_delay"
    ERROR = "error"
    WARNING = "warning"


# `message` positional, then arbitrary structured payload (business_name=...,
# seconds=...) — kept loose here since scrapers stay decoupled from the
# worker-layer schema; the worker's adapter maps this onto DiscoveryEventType.
ScrapeEventCallback = Callable[[ScrapeEventType, str, dict[str, Any]], Awaitable[None]]
ShouldStopCallback = Callable[[], Awaitable[bool]]

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
    # On-disk Chromium profile directory, keyed by scraper source — see
    # _launch_persistent_context for why this exists.
    profile_dir: str = "browser_profiles"

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


class CaptchaDetectedError(ScraperError):
    """Raised when a CAPTCHA/anti-bot interstitial is detected instead of the
    page actually navigated to. Deliberately not worth retrying — the block
    doesn't clear itself within a single job, so with_retry fails fast on
    this instead of burning its normal retry budget against it."""


class JobStoppedError(Exception):
    """Raised when a user-requested stop is observed mid-scrape.

    Deliberately NOT a ScraperError subclass — a stop is not a scrape
    failure, and must not trigger the anti-bot cooldown escalation the way a
    real CAPTCHA/timeout/selector-change does (see discovery_worker.py's
    _run_browser_scrape_job, which checks for this before ScraperError)."""


_CAPTCHA_URL_MARKERS = ("google.com/sorry", "/sorry/index")
_CAPTCHA_CONTENT_MARKERS = (
    "unusual traffic from your computer network",
    'id="captcha-form"',
    "g-recaptcha",
    "recaptcha/api.js",
)


class BaseScraper(ABC):
    """Shared Playwright lifecycle, stealth setup, and human-behavior helpers.

    Subclasses implement `scrape()` for a specific source (Google Maps, Facebook)
    and call the protected helpers below for navigation/interaction.
    """

    source: str

    def __init__(
        self,
        config: ScraperConfig | None = None,
        *,
        on_event: ScrapeEventCallback | None = None,
        on_check_stop: ShouldStopCallback | None = None,
    ) -> None:
        self.config = config or ScraperConfig()
        self._on_event = on_event
        self._on_check_stop = on_check_stop

    # ---- progress reporting / cooperative cancellation -------------------

    async def _emit(self, event_type: ScrapeEventType, message: str, **payload: Any) -> None:
        """Report a progress event to the caller-supplied callback, if any.

        Swallowed on failure — a reporting hiccup must never break the
        scrape, the same guarantee JobTracker itself makes on the other end.
        """
        if self._on_event is None:
            return
        try:
            await self._on_event(event_type, message, payload)
        except Exception as exc:  # noqa: BLE001 - reporting must never break the scrape
            logger.warning("Failed to emit scrape event %r: %s", event_type, exc)

    async def _check_stop(self) -> None:
        """Raise JobStoppedError if the caller-supplied stop check reports
        the job was cancelled. A no-op when no callback was supplied."""
        if self._on_check_stop is None:
            return
        if await self._on_check_stop():
            raise JobStoppedError(f"{self.source} scraper stopped by user request")

    # ---- lifecycle -----------------------------------------------------

    @asynccontextmanager
    async def browser_session(self, playwright: Playwright) -> AsyncIterator[BrowserContext]:
        context = await self._launch_persistent_context(playwright)
        context.set_default_navigation_timeout(self.config.navigation_timeout_ms)
        context.set_default_timeout(self.config.navigation_timeout_ms)
        try:
            yield context
        finally:
            await context.close()

    async def _launch_persistent_context(self, playwright: Playwright) -> BrowserContext:
        """Launch with an on-disk Chromium profile instead of a fresh,
        throwaway context every run.

        No proxy budget means no IP rotation — this doesn't address that.
        What it does address: a brand-new, cookie-less, history-less session
        on *every single run* is itself a bot signal Google/Facebook weigh,
        independent of IP. Reusing a profile across runs means cookies and
        local storage accumulate like a real recurring visitor's would.
        Keyed by `self.source` so Google Maps and Facebook keep separate
        profiles rather than sharing one.
        """
        profile_path = Path(self.config.profile_dir) / self.source
        profile_path.mkdir(parents=True, exist_ok=True)
        user_agent = random.choice(self.config.user_agents)
        return await playwright.chromium.launch_persistent_context(
            str(profile_path),
            headless=self.config.headless,
            viewport=self.config.viewport,
            user_agent=user_agent,
            locale=self.config.locale,
            timezone_id=self.config.timezone_id,
            geolocation=self.config.geolocation,
            permissions=["geolocation"],
            proxy=self.config.proxy,
            # --no-sandbox deliberately omitted: this worker runs on the
            # operator machine alongside production DB credentials and an
            # authenticated Cloud SQL Auth Proxy session, so the OS sandbox
            # is the last containment layer between a renderer exploit on a
            # scraped page and that host. It's a container-only workaround
            # this deployment doesn't need. See SecurityIssues.md M-7.
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

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

    async def rate_limit_delay(self) -> float:
        delay = random.uniform(self.config.rate_limit_min, self.config.rate_limit_max)
        await asyncio.sleep(delay)
        return delay

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

    # ---- bot-detection ----------------------------------------------------

    async def detect_captcha(self, page: Page) -> None:
        """Raise CaptchaDetectedError if `page` is a CAPTCHA/anti-bot
        interstitial rather than the page actually navigated to.

        Call this right after navigation, before waiting on a real selector —
        a CAPTCHA page is still a 200 OK, so without this check the caller
        would otherwise sit out a full navigation_timeout_ms waiting for a
        selector that will never appear, then retry into the same wall.
        """
        url = page.url.lower()
        if any(marker in url for marker in _CAPTCHA_URL_MARKERS):
            raise CaptchaDetectedError(f"CAPTCHA interstitial URL: {page.url}")

        try:
            content = (await page.content()).lower()
        except Exception:
            return  # can't confirm either way — let the normal selector wait decide
        if any(marker in content for marker in _CAPTCHA_CONTENT_MARKERS):
            raise CaptchaDetectedError(f"CAPTCHA markers found on {page.url}")

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
        retries are exhausted. CaptchaDetectedError is the one exception that
        skips this entirely — a CAPTCHA doesn't clear itself mid-job, so
        retrying against it just wastes the retry budget and looks even more
        like a bot; it's raised immediately on the first occurrence instead.
        """
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                return await func()
            except CaptchaDetectedError:
                logger.error("%s: CAPTCHA/interstitial detected — aborting without retrying", op_name)
                if page is not None:
                    await self.screenshot_on_failure(page, op_name)
                raise
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
