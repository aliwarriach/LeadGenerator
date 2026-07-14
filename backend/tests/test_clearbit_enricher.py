import httpx

from app.enrichers.clearbit_enricher import validate_logo


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_validate_logo_returns_none_without_domain():
    client = _client_with_handler(lambda request: httpx.Response(200))
    result = await validate_logo(
        client, None, base_url="https://logo.clearbit.com", timeout_seconds=5
    )
    assert result is None


async def test_validate_logo_returns_true_on_200():
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://logo.clearbit.com/example.com"
        return httpx.Response(200)

    client = _client_with_handler(handler)
    result = await validate_logo(
        client, "example.com", base_url="https://logo.clearbit.com", timeout_seconds=5
    )
    assert result is True


async def test_validate_logo_returns_false_on_404():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = _client_with_handler(handler)
    result = await validate_logo(
        client, "nonexistent-domain.example", base_url="https://logo.clearbit.com", timeout_seconds=5
    )
    assert result is False


async def test_validate_logo_returns_none_on_request_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    client = _client_with_handler(handler)
    result = await validate_logo(
        client, "example.com", base_url="https://logo.clearbit.com", timeout_seconds=5
    )
    assert result is None
