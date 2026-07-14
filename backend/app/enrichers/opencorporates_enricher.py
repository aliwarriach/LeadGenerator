from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def validate_company(
    client: httpx.AsyncClient,
    name: str,
    *,
    api_key: str | None,
    base_url: str,
    timeout_seconds: float,
) -> bool | None:
    """Check whether a company matching `name` appears in OpenCorporates'
    registry.

    Returns None (unchecked) rather than False when no API key is configured
    or the lookup itself fails — that's distinct from a real "not found"
    (False), which only comes from a successful zero-result response.
    """
    if not api_key:
        return None

    params = {"q": name, "api_token": api_key}
    try:
        response = await client.get(base_url, params=params, timeout=timeout_seconds)
        if response.status_code == 429:
            logger.warning("OpenCorporates rate limit hit for %r", name)
            return None
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("OpenCorporates request failed for %r: %s", name, exc)
        return None

    try:
        total_count = data["results"]["total_count"]
    except (KeyError, TypeError) as exc:
        logger.warning("OpenCorporates response for %r missing expected fields: %s", name, exc)
        return None

    return total_count > 0
