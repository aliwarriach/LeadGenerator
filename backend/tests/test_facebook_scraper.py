from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.scrapers.base_scraper import ScrapeEventType, ScraperConfig, ScraperError
from app.scrapers.facebook_scraper import FacebookScraper


def _mock_page(hrefs: list[str | None]) -> MagicMock:
    """A fake Playwright Page exposing just enough of the locator API for
    _extract_website: page.locator(...).count() / .nth(i).get_attribute(...).
    """
    anchor = MagicMock()
    anchor.get_attribute = AsyncMock(side_effect=hrefs)

    locator = MagicMock()
    locator.count = AsyncMock(return_value=len(hrefs))
    locator.nth = MagicMock(return_value=anchor)

    page = MagicMock()
    page.locator = MagicMock(return_value=locator)
    return page


@pytest.mark.parametrize(
    "href",
    [
        "https://www.linkedin.com/company/urbanestimation/",
        "https://twitter.com/urbanestimation",
        "https://www.instagram.com/urbanestimation",
        "https://www.facebook.com/urbanestimation",
    ],
)
async def test_extract_website_skips_non_business_domains(href):
    scraper = FacebookScraper()
    page = _mock_page([href])
    assert await scraper._extract_website(page) is None


async def test_extract_website_returns_first_business_domain():
    scraper = FacebookScraper()
    page = _mock_page(
        ["https://www.linkedin.com/company/urbanestimation/", "https://urbanestimation.com/"]
    )
    assert await scraper._extract_website(page) == "https://urbanestimation.com/"


async def test_extract_website_unwraps_l_facebook_redirect_to_business_site():
    scraper = FacebookScraper()
    wrapped = "https://l.facebook.com/l.php?u=https%3A%2F%2Furbanestimation.com%2F&h=abc"
    page = _mock_page([wrapped])
    assert await scraper._extract_website(page) == "https://urbanestimation.com/"


async def test_extract_website_skips_l_facebook_redirect_to_social_profile():
    # Regression test: Facebook proxies outbound links (including a page's own
    # LinkedIn/Instagram links) through l.facebook.com/l.php?u=<target> — the
    # unwrapped target must still clear the business-domain check, otherwise a
    # LinkedIn company URL gets saved as the lead's "website".
    scraper = FacebookScraper()
    wrapped = (
        "https://l.facebook.com/l.php?u=https%3A%2F%2Fwww.linkedin.com"
        "%2Fcompany%2Furbanestimation%2F&h=abc"
    )
    page = _mock_page([wrapped])
    assert await scraper._extract_website(page) is None


def _empty_locator() -> MagicMock:
    loc = MagicMock()
    loc.first = loc
    loc.count = AsyncMock(return_value=0)
    loc.get_attribute = AsyncMock(return_value=None)
    loc.inner_text = AsyncMock(side_effect=Exception("no text"))
    return loc


def _mock_extract_page(name: str | None) -> MagicMock:
    h1_locator = MagicMock()
    h1_locator.first = h1_locator
    h1_locator.inner_text = AsyncMock(return_value=name or "")

    def locator(selector):
        if selector == "h1":
            return h1_locator
        return _empty_locator()

    page = MagicMock()
    page.locator = MagicMock(side_effect=locator)
    page.goto = AsyncMock()
    page.mouse = MagicMock()
    page.mouse.wheel = AsyncMock()
    return page


async def test_extract_page_emits_business_processing_event(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    events: list[tuple] = []

    async def on_event(event_type, message, payload):
        events.append((event_type, message, payload))

    scraper = FacebookScraper(on_event=on_event)
    page = _mock_extract_page("Bahu Plumbers")

    with (
        patch.object(scraper, "_meta_content", new=AsyncMock(return_value=None)),
        patch.object(scraper, "_safe_inner_text", new=AsyncMock(return_value=None)),
        patch.object(scraper, "_extract_category", new=AsyncMock(return_value=None)),
        patch.object(scraper, "_extract_website", new=AsyncMock(return_value=None)),
    ):
        lead = await scraper._extract_page(page, "https://facebook.com/x", "plumbers", "Karachi")

    assert lead["name"] == "Bahu Plumbers"
    assert (
        ScrapeEventType.BUSINESS_PROCESSING,
        'Scraping business "Bahu Plumbers"',
        {"business_name": "Bahu Plumbers"},
    ) in events


def _mock_about_page(about_body_text: str | None, *, goto_raises: bool = False) -> MagicMock:
    body_locator = MagicMock()
    body_locator.first = body_locator
    if about_body_text is None:
        body_locator.inner_text = AsyncMock(side_effect=Exception("no text"))
    else:
        body_locator.inner_text = AsyncMock(return_value=about_body_text)

    page = MagicMock()
    page.locator = MagicMock(return_value=body_locator)
    if goto_raises:
        page.goto = AsyncMock(side_effect=Exception("nav failed"))
    else:
        page.goto = AsyncMock()
    return page


async def test_extract_phone_from_about_finds_number_before_mobile_label(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    scraper = FacebookScraper()
    page = _mock_about_page("Service area\n0321 4141862\nMobile\nmore text")

    phone = await scraper._extract_phone_from_about(page, "https://www.facebook.com/marvelestate")

    assert phone == "0321 4141862"
    page.goto.assert_awaited_once_with(
        "https://www.facebook.com/marvelestate/about", wait_until="domcontentloaded"
    )


async def test_extract_phone_from_about_returns_none_without_label(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    scraper = FacebookScraper()
    page = _mock_about_page("Lahore, Punjab, Pakistan\nNo contact info here")

    assert await scraper._extract_phone_from_about(page, "https://www.facebook.com/x") is None


async def test_extract_phone_from_about_returns_none_on_navigation_failure(monkeypatch):
    monkeypatch.setattr("asyncio.sleep", AsyncMock())
    scraper = FacebookScraper()
    page = _mock_about_page(None, goto_raises=True)

    assert await scraper._extract_phone_from_about(page, "https://www.facebook.com/x") is None


async def test_safe_visit_page_emits_warning_on_failure():
    events: list[tuple] = []

    async def on_event(event_type, message, payload):
        events.append((event_type, message, payload))

    config = ScraperConfig(max_retries=1)
    scraper = FacebookScraper(config, on_event=on_event)

    with patch.object(scraper, "_extract_page", new=AsyncMock(side_effect=ScraperError("boom"))):
        result = await scraper._safe_visit_page(MagicMock(), "https://facebook.com/x", "plumbers", "Karachi")

    assert result is None
    assert any(event_type == ScrapeEventType.WARNING for event_type, _, _ in events)
