import httpx
import pytest

from app.scrapers.serper_worker import SerperConfig, SerperWorker


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_scrape_returns_empty_list_when_no_api_key():
    worker = SerperWorker(SerperConfig(api_key=None))
    results = await worker.scrape("plumbers", "Karachi")
    assert results == []


async def test_scrape_normalizes_organic_results():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-API-KEY"] == "test-key"
        return httpx.Response(
            200,
            json={
                "organic": [
                    {
                        "title": "Bahu Plumbers",
                        "link": "https://bahuplumbers.org/",
                        "snippet": "Call us now at +92 300 1234567 for fast service.",
                        "position": 1,
                    },
                    {
                        "title": "Bahu Plumbers Facebook Page",
                        "link": "https://facebook.com/bahuplumbers",
                        "snippet": "Follow us on Facebook.",
                        "position": 2,
                    },
                ]
            },
        )

    worker = SerperWorker(SerperConfig(api_key="test-key"), http_client=_client_with_handler(handler))
    results = await worker.scrape("plumbers", "Karachi")

    assert len(results) == 2

    real_site = results[0]
    assert real_site["name"] == "Bahu Plumbers"
    assert real_site["website"] == "https://bahuplumbers.org/"
    assert real_site["has_website"] is True
    assert real_site["phone"] == "+92 300 1234567"
    assert real_site["source"] == "serper"
    assert real_site["location"] == "Karachi"

    social_link = results[1]
    assert social_link["website"] is None
    assert social_link["has_website"] is False


async def test_scrape_skips_results_without_title():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"organic": [{"link": "https://example.com", "snippet": ""}]})

    worker = SerperWorker(SerperConfig(api_key="test-key"), http_client=_client_with_handler(handler))
    results = await worker.scrape("plumbers", "Karachi")
    assert results == []


async def test_scrape_retries_on_server_error_then_succeeds():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, json={"error": "server error"})
        return httpx.Response(200, json={"organic": [{"title": "Bahu Plumbers", "link": "https://bahuplumbers.org/"}]})

    worker = SerperWorker(
        SerperConfig(api_key="test-key", max_retries=3),
        http_client=_client_with_handler(handler),
    )
    results = await worker.scrape("plumbers", "Karachi")

    assert call_count == 2
    assert len(results) == 1
    assert results[0]["name"] == "Bahu Plumbers"


async def test_scrape_returns_empty_list_when_retries_exhausted():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "server error"})

    worker = SerperWorker(
        SerperConfig(api_key="test-key", max_retries=2),
        http_client=_client_with_handler(handler),
    )
    results = await worker.scrape("plumbers", "Karachi")
    assert results == []


async def test_scrape_treats_429_as_retryable():
    call_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json={"organic": []})

    worker = SerperWorker(
        SerperConfig(api_key="test-key", max_retries=3),
        http_client=_client_with_handler(handler),
    )
    results = await worker.scrape("plumbers", "Karachi")

    assert call_count == 2
    assert results == []
