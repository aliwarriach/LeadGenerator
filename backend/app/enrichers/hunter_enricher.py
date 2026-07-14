from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def find_emails(
    client: httpx.AsyncClient,
    domain: str | None,
    *,
    api_key: str | None,
    base_url: str,
    timeout_seconds: float,
    max_emails: int,
) -> list[str] | None:
    """Look up publicly indexed emails for `domain` via Hunter.io's domain search.

    Returns None if no API key is configured, no domain is available, the
    domain has no hits, or the request fails for any reason (quota
    exhausted, invalid domain, etc.) — Hunter is a bonus enrichment, never a
    hard dependency for saving a lead.
    """
    if not api_key or not domain:
        return None

    params = {"domain": domain, "api_key": api_key, "limit": max_emails}
    try:
        response = await client.get(base_url, params=params, timeout=timeout_seconds)
        if response.status_code == 429:
            logger.warning("Hunter.io rate limit hit for domain %s", domain)
            return None
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Hunter.io request failed for %s: %s", domain, exc)
        return None

    try:
        emails = [item["value"] for item in data["data"]["emails"] if item.get("value")]
    except (KeyError, TypeError) as exc:
        logger.warning("Hunter.io response for %s missing expected fields: %s", domain, exc)
        return None

    return emails[:max_emails] or None
