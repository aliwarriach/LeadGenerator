import ipaddress
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.url_guard import UnsafeUrlError, safe_get, validate_public_http_url

_PUBLIC = [ipaddress.ip_address("93.184.216.34")]


def _resolving_to(*addresses: str):
    return patch(
        "app.core.url_guard.resolve_host_addresses",
        new=AsyncMock(return_value=[ipaddress.ip_address(a) for a in addresses]),
    )


# ---- scheme / shape --------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "gopher://internal:70/",
        "ftp://internal/",
        # A common SSRF filter bypass — rejected on scheme before anything else.
        "http+unix://%2Fvar%2Frun%2Fdocker.sock/info",
    ],
)
async def test_non_http_schemes_are_rejected(url):
    with pytest.raises(UnsafeUrlError):
        await validate_public_http_url(url)


async def test_url_without_a_host_is_rejected():
    with pytest.raises(UnsafeUrlError):
        await validate_public_http_url("http:///no-host")


# ---- address policy --------------------------------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",  # loopback
        "10.1.2.3",  # RFC1918
        "192.168.0.10",  # RFC1918
        "172.16.5.4",  # RFC1918
        "169.254.169.254",  # cloud metadata endpoint
        "100.64.0.1",  # carrier-grade NAT
        "0.0.0.0",  # unspecified
        "::1",  # IPv6 loopback
        "fd00::1",  # IPv6 unique-local
        "fe80::1",  # IPv6 link-local
    ],
)
async def test_non_public_addresses_are_rejected(address):
    with _resolving_to(address):
        with pytest.raises(UnsafeUrlError):
            await validate_public_http_url("http://anything.example")


async def test_public_address_is_accepted():
    with _resolving_to("93.184.216.34"):
        await validate_public_http_url("https://example.com/page")


async def test_literal_public_ip_is_accepted_without_dns():
    # No resolver patch: a literal IP must not need a lookup at all.
    await validate_public_http_url("http://93.184.216.34/status")


async def test_literal_private_ip_is_rejected_without_dns():
    with pytest.raises(UnsafeUrlError):
        await validate_public_http_url("http://169.254.169.254/computeMetadata/v1/")


async def test_host_resolving_to_both_public_and_private_is_rejected():
    """One private answer poisons the host — which address httpx picks when it
    resolves again is not under this code's control."""
    with _resolving_to("93.184.216.34", "10.0.0.7"):
        with pytest.raises(UnsafeUrlError):
            await validate_public_http_url("http://split-horizon.example")


async def test_unresolvable_host_is_rejected():
    with patch(
        "app.core.url_guard.resolve_host_addresses",
        new=AsyncMock(side_effect=UnsafeUrlError("Could not resolve host")),
    ):
        with pytest.raises(UnsafeUrlError):
            await validate_public_http_url("http://does-not-exist.example")


# ---- safe_get / redirects --------------------------------------------------


async def test_safe_get_returns_a_non_redirect_response():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with _resolving_to("93.184.216.34"):
        response = await safe_get(client, "https://example.com", timeout=5)

    assert response.status_code == 200
    assert response.text == "ok"


async def test_safe_get_follows_a_redirect_to_another_public_host():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(301, headers={"location": "https://example.com/final"})
        return httpx.Response(200, text="arrived")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with _resolving_to("93.184.216.34"):
        response = await safe_get(client, "https://example.com/", timeout=5)

    assert response.text == "arrived"


async def test_safe_get_rejects_a_redirect_into_a_private_address():
    """The whole reason redirects are followed by hand: a public URL that
    bounces to the metadata endpoint must never be fetched."""
    requested: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    # Literal IPs throughout: patching the resolver would make *every* host
    # look public, including the redirect target this test is about.
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(UnsafeUrlError):
        await safe_get(client, "https://93.184.216.34/", timeout=5)

    assert requested == ["https://93.184.216.34/"]


async def test_safe_get_resolves_a_relative_redirect_target():
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "/end"})
        return httpx.Response(200, text="relative ok")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with _resolving_to("93.184.216.34"):
        response = await safe_get(client, "https://example.com/start", timeout=5)

    assert response.text == "relative ok"


async def test_safe_get_gives_up_on_a_redirect_loop():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.com/loop"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with _resolving_to("93.184.216.34"):
        with pytest.raises(UnsafeUrlError):
            await safe_get(client, "https://example.com/loop", timeout=5)


async def test_safe_get_returns_a_redirect_that_carries_no_location():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with _resolving_to("93.184.216.34"):
        response = await safe_get(client, "https://example.com", timeout=5)

    assert response.status_code == 302
