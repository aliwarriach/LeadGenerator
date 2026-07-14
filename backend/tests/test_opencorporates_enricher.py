import httpx

from app.enrichers.opencorporates_enricher import validate_company


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_validate_company_returns_none_without_api_key():
    client = _client_with_handler(lambda request: httpx.Response(200, json={}))
    result = await validate_company(
        client, "Acme Inc", api_key=None,
        base_url="https://api.opencorporates.com/v0.4/companies/search", timeout_seconds=5,
    )
    assert result is None


async def test_validate_company_returns_true_when_matches_found():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {"total_count": 3}})

    client = _client_with_handler(handler)
    result = await validate_company(
        client, "Acme Inc", api_key="key",
        base_url="https://api.opencorporates.com/v0.4/companies/search", timeout_seconds=5,
    )
    assert result is True


async def test_validate_company_returns_false_when_no_matches():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {"total_count": 0}})

    client = _client_with_handler(handler)
    result = await validate_company(
        client, "Nonexistent Corp", api_key="key",
        base_url="https://api.opencorporates.com/v0.4/companies/search", timeout_seconds=5,
    )
    assert result is False


async def test_validate_company_returns_none_on_rate_limit():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    client = _client_with_handler(handler)
    result = await validate_company(
        client, "Acme Inc", api_key="key",
        base_url="https://api.opencorporates.com/v0.4/companies/search", timeout_seconds=5,
    )
    assert result is None


async def test_validate_company_returns_none_on_malformed_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    client = _client_with_handler(handler)
    result = await validate_company(
        client, "Acme Inc", api_key="key",
        base_url="https://api.opencorporates.com/v0.4/companies/search", timeout_seconds=5,
    )
    assert result is None
