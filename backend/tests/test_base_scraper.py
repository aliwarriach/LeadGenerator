from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.scrapers.base_scraper import BaseScraper, ScraperConfig, ScraperError


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
