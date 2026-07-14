import httpx

from app.enrichers.hunter_enricher import find_emails


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_find_emails_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    emails = await find_emails(
        client, "example.com", api_key=None, base_url="https://api.hunter.io/v2/domain-search",
        timeout_seconds=5, max_emails=3,
    )
    assert emails is None


async def test_find_emails_returns_none_without_domain():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    emails = await find_emails(
        client, None, api_key="key", base_url="https://api.hunter.io/v2/domain-search",
        timeout_seconds=5, max_emails=3,
    )
    assert emails is None


async def test_find_emails_parses_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"emails": [{"value": "info@example.com"}, {"value": "sales@example.com"}]}},
        )

    client = _client_with_handler(handler)
    emails = await find_emails(
        client, "example.com", api_key="key", base_url="https://api.hunter.io/v2/domain-search",
        timeout_seconds=5, max_emails=3,
    )
    assert emails == ["info@example.com", "sales@example.com"]


async def test_find_emails_respects_max_emails():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": {"emails": [{"value": f"user{i}@example.com"} for i in range(5)]}},
        )

    client = _client_with_handler(handler)
    emails = await find_emails(
        client, "example.com", api_key="key", base_url="https://api.hunter.io/v2/domain-search",
        timeout_seconds=5, max_emails=2,
    )
    assert emails == ["user0@example.com", "user1@example.com"]


async def test_find_emails_returns_none_on_rate_limit():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate limited"})

    client = _client_with_handler(handler)
    emails = await find_emails(
        client, "example.com", api_key="key", base_url="https://api.hunter.io/v2/domain-search",
        timeout_seconds=5, max_emails=3,
    )
    assert emails is None


async def test_find_emails_returns_none_on_malformed_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client_with_handler(handler)
    emails = await find_emails(
        client, "example.com", api_key="key", base_url="https://api.hunter.io/v2/domain-search",
        timeout_seconds=5, max_emails=3,
    )
    assert emails is None
