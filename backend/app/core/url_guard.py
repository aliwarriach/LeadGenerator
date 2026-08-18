"""SSRF protection for server-side fetches of lead-supplied URLs.

`Lead.website` is not trustworthy input: it arrives from scraped listings today
and will be user-settable once manual lead creation exists. Two enrichers fetch
it directly from the API process (`website_content_enricher`,
`wappalyzer_enricher`), and that process runs inside a VPC with internal
services reachable — so an attacker-chosen URL is a request forgery primitive
against the internal network.

`safe_get` is the only way those two should fetch. It validates the target
before connecting *and* re-validates every redirect hop, because
`follow_redirects=True` otherwise lets a public URL bounce straight to
169.254.169.254 or an internal host.

Known limitation: validation resolves DNS and then httpx resolves it again to
connect, so a DNS-rebinding attacker could in principle return a public address
on the first lookup and a private one on the second. Closing that needs
connecting by IP with a Host/SNI override, which breaks TLS verification for
the common case. The check below stops the entire realistic attack — a URL that
simply points somewhere internal — and the rebinding variant is accepted.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})

# Enough for the usual http→https and apex→www chains without letting a
# redirect loop burn the request timeout.
_MAX_REDIRECTS = 5

# A few MB is generous for the HTML/headers this fetches (page audits,
# Wappalyzer fingerprinting) and well below anything that threatens a Cloud
# Run instance's memory. Neither caller capped this before — see
# SecurityIssues.md M-6.
_DEFAULT_MAX_RESPONSE_BYTES = 5 * 1024 * 1024


class UnsafeUrlError(Exception):
    """The URL is malformed, uses a non-HTTP scheme, or resolves to an address
    the application must never fetch."""


def _is_forbidden_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # `is_global` already excludes private, loopback, link-local (which covers
    # the 169.254.169.254 cloud metadata endpoint), multicast, reserved, and
    # the 100.64/10 carrier-grade NAT range. The explicit checks after it are
    # belt-and-braces for address kinds whose `is_global` has shifted between
    # Python releases.
    return not ip.is_global or ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved


async def resolve_host_addresses(host: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    """Every address `host` resolves to. A literal IP resolves to itself.

    Public, and the documented seam tests patch: it is the only part of this
    module that touches the network, so patching it keeps unit tests off DNS
    without stubbing out the policy being tested.
    """
    try:
        return [ipaddress.ip_address(host)]
    except ValueError:
        pass

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Could not resolve host {host!r}") from exc

    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue

    if not addresses:
        raise UnsafeUrlError(f"Host {host!r} resolved to no usable address")
    return addresses


async def validate_public_http_url(url: str) -> None:
    """Raise `UnsafeUrlError` unless `url` is an http(s) URL whose every
    resolved address is publicly routable.

    Every address is checked, not just the first: a host with both a public
    A record and a private one must be rejected, since which one httpx picks
    is not under this code's control.
    """
    parsed = urlparse(url)

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"Scheme {parsed.scheme!r} is not allowed — only http and https")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError(f"URL {url!r} has no host")

    for address in await resolve_host_addresses(host):
        if _is_forbidden_address(address):
            raise UnsafeUrlError(f"Host {host!r} resolves to non-public address {address}")


async def _read_capped(response: httpx.Response, max_bytes: int) -> httpx.Response:
    """Reads `response`'s streamed body into a bounded buffer, aborting once
    it exceeds `max_bytes` — a server that lies about (or omits)
    Content-Length and simply keeps sending bytes must not be allowed to
    exhaust process memory (SecurityIssues.md M-6). Returns a fully-read
    Response built from the capped bytes, so `.text`/`.json()` work
    normally on the result.
    """
    content_length = response.headers.get("content-length")
    if content_length is not None and content_length.isdigit() and int(content_length) > max_bytes:
        await response.aclose()
        raise UnsafeUrlError(f"Response declared {content_length} bytes, exceeding the {max_bytes}-byte limit")

    data = bytearray()
    async for chunk in response.aiter_bytes():
        data.extend(chunk)
        if len(data) > max_bytes:
            await response.aclose()
            raise UnsafeUrlError(f"Response body exceeded the {max_bytes}-byte limit")

    await response.aclose()
    return httpx.Response(
        status_code=response.status_code,
        headers=response.headers,
        content=bytes(data),
        request=response.request,
    )


async def _fetch_hop(client: httpx.AsyncClient, url: str, timeout: float, max_bytes: int) -> httpx.Response:
    request = client.build_request("GET", url, timeout=timeout)
    response = await client.send(request, stream=True, follow_redirects=False)

    if response.status_code in _REDIRECT_STATUS_CODES:
        # Headers (including Location) are already available once the
        # response starts — no need to read the (likely empty) redirect body.
        await response.aclose()
        return response

    return await _read_capped(response, max_bytes)


async def safe_get(
    client: httpx.AsyncClient, url: str, *, timeout: float, max_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES
) -> httpx.Response:
    """GET `url`, validating it and every redirect target first.

    Redirects are followed manually — `follow_redirects=True` would hand the
    final hop to httpx unchecked, which is exactly the hole this closes.
    Raises `UnsafeUrlError` for a rejected target, an oversized response body
    (see `_read_capped`), or any `httpx` error the caller already handles.

    Each hop is wrapped in a `timeout`-second wall-clock deadline covering
    the *whole* download, not just each individual read: httpx's `timeout`
    only bounds a single I/O operation, so a server that trickles a few
    bytes at a time — never going long enough between them to trip a
    per-operation read timeout — would otherwise never be cut off.
    """
    current = url
    for _ in range(_MAX_REDIRECTS + 1):
        await validate_public_http_url(current)
        response = await asyncio.wait_for(_fetch_hop(client, current, timeout, max_bytes), timeout=timeout)

        if response.status_code not in _REDIRECT_STATUS_CODES:
            return response

        location = response.headers.get("location")
        if not location:
            # A redirect status with no target — nothing to follow, so hand the
            # response back and let the caller's raise_for_status deal with it.
            return response

        current = urljoin(current, location)
        logger.debug("Following redirect to %s", current)

    raise UnsafeUrlError(f"URL {url!r} exceeded {_MAX_REDIRECTS} redirects")
