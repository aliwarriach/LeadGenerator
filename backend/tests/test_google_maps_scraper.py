from unittest.mock import AsyncMock, MagicMock, patch

from app.scrapers.base_scraper import ScrapeEventType, ScraperConfig, ScraperError
from app.scrapers.google_maps_scraper import GoogleMapsScraper


def _lead(rating: float | None) -> dict:
    return {"name": "Bahu Plumbers", "raw_data": {"rating": rating}}


def test_meets_rating_threshold_passes_when_no_min_rating_given():
    assert GoogleMapsScraper._meets_rating_threshold(_lead(3.0), None) is True
    assert GoogleMapsScraper._meets_rating_threshold(_lead(None), None) is True


def test_meets_rating_threshold_passes_when_rating_at_or_above_minimum():
    assert GoogleMapsScraper._meets_rating_threshold(_lead(4.5), 4.5) is True
    assert GoogleMapsScraper._meets_rating_threshold(_lead(4.9), 4.5) is True


def test_meets_rating_threshold_fails_when_rating_below_minimum():
    assert GoogleMapsScraper._meets_rating_threshold(_lead(4.2), 4.5) is False


def test_meets_rating_threshold_fails_when_no_rating_available():
    # A listing with no rating at all can't be confirmed to meet the
    # threshold, so it's excluded rather than assumed to pass.
    assert GoogleMapsScraper._meets_rating_threshold(_lead(None), 4.0) is False


def _empty_locator() -> MagicMock:
    """A locator that reports zero matches for every extraction helper's
    `count()` guard, so website/address/phone/rating all resolve to None."""
    loc = MagicMock()
    loc.first = loc
    loc.count = AsyncMock(return_value=0)
    loc.get_attribute = AsyncMock(return_value=None)
    loc.inner_text = AsyncMock(side_effect=Exception("no text"))
    return loc


def _mock_place_page(name: str | None) -> MagicMock:
    h1_last = MagicMock()
    h1_last.count = AsyncMock(return_value=1 if name else 0)
    h1_last.inner_text = AsyncMock(return_value=name or "")

    h1_wrapper = MagicMock()
    h1_wrapper.last = h1_last

    def locator(selector):
        if selector == "h1":
            return h1_wrapper
        return _empty_locator()

    page = MagicMock()
    page.locator = MagicMock(side_effect=locator)
    page.url = "https://www.google.com/maps/place/test"
    return page


async def test_extract_place_details_emits_business_processing_event():
    events: list[tuple] = []

    async def on_event(event_type, message, payload):
        events.append((event_type, message, payload))

    scraper = GoogleMapsScraper(on_event=on_event)
    page = _mock_place_page("Bahu Plumbers")

    lead = await scraper._extract_place_details(page, "plumbers", "Karachi")

    assert lead["name"] == "Bahu Plumbers"
    assert (
        ScrapeEventType.BUSINESS_PROCESSING,
        'Scraping business "Bahu Plumbers"',
        {"business_name": "Bahu Plumbers"},
    ) in events


async def test_extract_place_details_raises_without_emitting_when_no_name():
    events: list[tuple] = []

    async def on_event(event_type, message, payload):
        events.append((event_type, message, payload))

    scraper = GoogleMapsScraper(on_event=on_event)
    page = _mock_place_page(None)

    try:
        await scraper._extract_place_details(page, "plumbers", "Karachi")
        assert False, "expected ScraperError"
    except ScraperError:
        pass

    assert events == []


async def test_safe_extract_listing_emits_warning_on_failure():
    events: list[tuple] = []

    async def on_event(event_type, message, payload):
        events.append((event_type, message, payload))

    config = ScraperConfig(max_retries=1)
    scraper = GoogleMapsScraper(config, on_event=on_event)

    with patch.object(scraper, "_extract_listing", new=AsyncMock(side_effect=ScraperError("boom"))):
        result = await scraper._safe_extract_listing(MagicMock(), MagicMock(), "plumbers", "Karachi")

    assert result is None
    assert any(event_type == ScrapeEventType.WARNING for event_type, _, _ in events)
