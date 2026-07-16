from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.scrapers.base_scraper import (
    BaseScraper,
    CaptchaDetectedError,
    JobStoppedError,
    ScrapeEventType,
    ScraperConfig,
    ScraperError,
)


class _FakePage:
    def __init__(self, url: str, html: str = "<html><body>ok</body></html>") -> None:
        self.url = url
        self._html = html

    async def content(self) -> str:
        return self._html


class _DummyScraper(BaseScraper):
    source = "dummy"

    async def scrape(self, query: str, location: str) -> list[dict[str, Any]]:
        return []


@pytest.fixture
def scraper() -> _DummyScraper:
    # Zeroed-out delays keep retry tests fast without touching asyncio.sleep internals.
    config = ScraperConfig(max_retries=3, action_delay_min=0, action_delay_max=0)
    return _DummyScraper(config)


async def test_with_retry_returns_on_first_success(scraper, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await scraper.with_retry(op, op_name="test_op")

    assert result == "ok"
    assert call_count == 1


async def test_with_retry_succeeds_after_transient_failures(scraper, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise RuntimeError("transient")
        return "ok"

    result = await scraper.with_retry(op, op_name="test_op")

    assert result == "ok"
    assert call_count == 3


async def test_with_retry_raises_scraper_error_after_exhausting_attempts(scraper, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("always fails")

    with pytest.raises(ScraperError):
        await scraper.with_retry(op, op_name="test_op")

    assert call_count == scraper.config.max_retries


async def test_detect_captcha_raises_on_google_sorry_url(scraper):
    page = _FakePage("https://www.google.com/sorry/index?continue=https://www.google.com/maps")
    with pytest.raises(CaptchaDetectedError):
        await scraper.detect_captcha(page)


async def test_detect_captcha_raises_on_recaptcha_markup(scraper):
    page = _FakePage(
        "https://www.google.com/search?q=test",
        html="<html><body><div class='g-recaptcha'></div></body></html>",
    )
    with pytest.raises(CaptchaDetectedError):
        await scraper.detect_captcha(page)


async def test_detect_captcha_passes_for_normal_page(scraper):
    page = _FakePage(
        "https://www.google.com/maps/search/plumbers+in+Karachi",
        html="<html><body>normal search results</body></html>",
    )
    await scraper.detect_captcha(page)  # must not raise


async def test_with_retry_fails_fast_on_captcha_without_retrying(scraper, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    call_count = 0

    async def op():
        nonlocal call_count
        call_count += 1
        raise CaptchaDetectedError("blocked")

    with pytest.raises(CaptchaDetectedError):
        await scraper.with_retry(op, op_name="test_op")

    assert call_count == 1  # no retries burned against a CAPTCHA that won't clear


async def test_launch_persistent_context_uses_source_keyed_profile_dir(tmp_path):
    config = ScraperConfig(profile_dir=str(tmp_path))
    scraper = _DummyScraper(config)

    fake_context = AsyncMock()
    playwright = AsyncMock()
    playwright.chromium.launch_persistent_context = AsyncMock(return_value=fake_context)

    result = await scraper._launch_persistent_context(playwright)

    assert result is fake_context
    expected_path = tmp_path / "dummy"  # _DummyScraper.source == "dummy"
    assert expected_path.is_dir()  # created if missing
    call_args = playwright.chromium.launch_persistent_context.call_args
    assert call_args.args[0] == str(expected_path)


async def test_normalize_marks_has_website_from_website_presence(scraper):
    with_site = scraper.normalize(
        name=" Joe's Plumbing ", location="Karachi", website=" https://joes.example ", phone=None, raw_data={}
    )
    without_site = scraper.normalize(
        name="Joe's Plumbing", location="Karachi", website=None, phone=None, raw_data={}
    )

    assert with_site["has_website"] is True
    assert with_site["website"] == "https://joes.example"
    assert with_site["name"] == "Joe's Plumbing"
    assert without_site["has_website"] is False
    assert without_site["website"] is None


def _config() -> ScraperConfig:
    return ScraperConfig(max_retries=3, action_delay_min=0, action_delay_max=0)


async def test_emit_is_noop_when_no_callback_configured(scraper):
    await scraper._emit(ScrapeEventType.WARNING, "should not raise")


async def test_emit_invokes_configured_callback():
    events: list[tuple] = []

    async def on_event(event_type, message, payload):
        events.append((event_type, message, payload))

    scraper = _DummyScraper(_config(), on_event=on_event)
    await scraper._emit(ScrapeEventType.BUSINESS_PROCESSING, "Scraping X", business_name="X")

    assert events == [(ScrapeEventType.BUSINESS_PROCESSING, "Scraping X", {"business_name": "X"})]


async def test_emit_swallows_callback_failure():
    async def on_event(event_type, message, payload):
        raise RuntimeError("boom")

    scraper = _DummyScraper(_config(), on_event=on_event)
    await scraper._emit(ScrapeEventType.WARNING, "should not raise")  # must not propagate


async def test_check_stop_is_noop_when_no_callback_configured(scraper):
    await scraper._check_stop()


async def test_check_stop_raises_job_stopped_error_when_callback_reports_stop():
    scraper = _DummyScraper(_config(), on_check_stop=AsyncMock(return_value=True))

    with pytest.raises(JobStoppedError):
        await scraper._check_stop()


async def test_check_stop_does_not_raise_when_callback_reports_continue():
    scraper = _DummyScraper(_config(), on_check_stop=AsyncMock(return_value=False))

    await scraper._check_stop()  # must not raise


async def test_rate_limit_delay_returns_sampled_delay(scraper, monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    delay = await scraper.rate_limit_delay()

    assert scraper.config.rate_limit_min <= delay <= scraper.config.rate_limit_max
