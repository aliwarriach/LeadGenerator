from __future__ import annotations

import asyncio
import logging
import warnings

import httpx
from Wappalyzer import Wappalyzer, WebPage

from app.core.url_guard import safe_get

logger = logging.getLogger(__name__)

_analyzer: Wappalyzer | None = None


def _get_analyzer() -> Wappalyzer:
    # Wappalyzer.latest() loads the bundled technologies.json ruleset (no
    # network call) — cache it process-wide since parsing it isn't free and
    # it's immutable for the process lifetime. The ruleset has a few
    # malformed regexes that raise a UserWarning during pattern compilation
    # here (known upstream data issue, not fixable from this side).
    global _analyzer
    if _analyzer is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _analyzer = Wappalyzer.latest()
    return _analyzer


async def detect_tech_stack(
    client: httpx.AsyncClient,
    website: str,
    *,
    fetch_timeout_seconds: float,
) -> list[str] | None:
    """Fetch `website` and fingerprint its tech stack against Wappalyzer's
    bundled ruleset — local pattern matching on the fetched HTML/headers,
    no external API or key involved.
    """
    try:
        # safe_get, not client.get — `website` is untrusted input fetched from
        # inside the VPC. See app/core/url_guard.py.
        response = await safe_get(client, website, timeout=fetch_timeout_seconds)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Wappalyzer fetch failed for %s: %s", website, exc)
        return None

    try:
        webpage = WebPage(str(response.url), response.text, dict(response.headers))
        analyzer = _get_analyzer()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            technologies = await asyncio.to_thread(analyzer.analyze, webpage)
    except Exception as exc:  # noqa: BLE001 - enrichment failures must never propagate
        logger.warning("Wappalyzer analysis failed for %s: %s", website, exc)
        return None

    return sorted(technologies) or None
