from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def validate_logo(
    client: httpx.AsyncClient,
    domain: str | None,
    *,
    base_url: str,
    timeout_seconds: float,
) -> bool | None:
    """Quick, keyless domain sanity check: Clearbit's Logo API 200s for
    domains it recognizes and 404s otherwise.

    Returns None (unchecked) only if the request itself fails or no domain
    is available — a real 404 response is a definite False.
    """
    if not domain:
        return None

    url = f"{base_url}/{domain}"
    try:
        response = await client.get(url, timeout=timeout_seconds, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Clearbit logo check failed for %s: %s", domain, exc)
        return None

    return response.status_code == 200
