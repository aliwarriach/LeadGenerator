import httpx

from app.enrichers.wappalyzer_enricher import detect_tech_stack


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_detect_tech_stack_identifies_wordpress_from_html():
    html = (
        "<html><head>"
        '<meta name="generator" content="WordPress 6.4">'
        '<script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>'
        "</head><body>hi</body></html>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})

    client = _client_with_handler(handler)
    tech = await detect_tech_stack(client, "https://example.com", fetch_timeout_seconds=10)

    assert tech is not None
    assert "WordPress" in tech
    assert "jQuery" in tech


async def test_detect_tech_stack_returns_none_on_fetch_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_handler(handler)
    tech = await detect_tech_stack(client, "https://example.com", fetch_timeout_seconds=10)
    assert tech is None


async def test_detect_tech_stack_returns_none_when_no_technologies_match():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html><body>plain page</body></html>")

    client = _client_with_handler(handler)
    tech = await detect_tech_stack(client, "https://example.com", fetch_timeout_seconds=10)
    assert tech is None
