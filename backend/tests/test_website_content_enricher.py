import httpx

from app.enrichers.website_content_enricher import extract_content


def _client_with_handler(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_extract_content_parses_title_meta_headings_and_text():
    html = (
        "<html><head>"
        "<title>Bahu Plumbers | Karachi</title>"
        '<meta name="description" content="Fast, reliable plumbing in Karachi.">'
        "</head><body>"
        "<h1>Welcome to Bahu Plumbers</h1>"
        "<h2>Our Services</h2>"
        "<p>We fix leaks, install fixtures, and more.</p>"
        "</body></html>"
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html, headers={"Content-Type": "text/html"})

    client = _client_with_handler(handler)
    content = await extract_content(client, "https://bahuplumbers.example", fetch_timeout_seconds=10, max_chars=3000)

    assert content is not None
    assert content["title"] == "Bahu Plumbers | Karachi"
    assert content["meta_description"] == "Fast, reliable plumbing in Karachi."
    assert content["headings"] == ["Welcome to Bahu Plumbers", "Our Services"]
    assert "We fix leaks" in content["text_sample"]


async def test_extract_content_handles_missing_title_and_meta():
    html = "<html><body><p>Just some text.</p></body></html>"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = _client_with_handler(handler)
    content = await extract_content(client, "https://example.com", fetch_timeout_seconds=10, max_chars=3000)

    assert content is not None
    assert content["title"] is None
    assert content["meta_description"] is None
    assert content["headings"] == []


async def test_extract_content_truncates_text_sample_to_max_chars():
    html = f"<html><body><p>{'a' * 5000}</p></body></html>"

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=html)

    client = _client_with_handler(handler)
    content = await extract_content(client, "https://example.com", fetch_timeout_seconds=10, max_chars=100)

    assert content is not None
    assert len(content["text_sample"]) == 100


async def test_extract_content_returns_none_on_fetch_failure():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client_with_handler(handler)
    content = await extract_content(client, "https://example.com", fetch_timeout_seconds=10, max_chars=3000)

    assert content is None
