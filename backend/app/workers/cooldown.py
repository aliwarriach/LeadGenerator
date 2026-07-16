from __future__ import annotations

import logging

from arq.connections import ArqRedis

logger = logging.getLogger(__name__)

_COOLDOWN_KEY = "scraper:cooldown:{source}"
_STRIKES_KEY = "scraper:strikes:{source}"

# Escalating cooldown: one blip shouldn't idle a source for hours, but repeated
# failures back off hard instead of continuing to hammer an already-flagged IP.
BASE_COOLDOWN_SECONDS = 5 * 60
MAX_COOLDOWN_SECONDS = 4 * 60 * 60

# A confirmed CAPTCHA is a much stronger block signal than a generic search
# failure (timeout, layout change, network blip) — start the escalation much
# higher rather than treating both the same.
CAPTCHA_BASE_COOLDOWN_SECONDS = 30 * 60


async def seconds_remaining(redis: ArqRedis, source: str) -> int | None:
    """Remaining cooldown for `source`, or None if it's clear to run now."""
    ttl = await redis.ttl(_COOLDOWN_KEY.format(source=source))
    return ttl if ttl and ttl > 0 else None


async def record_failure(redis: ArqRedis, source: str, *, base_seconds: int = BASE_COOLDOWN_SECONDS) -> int:
    """Record a scrape failure for `source`, putting it into cooldown.

    Each consecutive strike (since the last record_success) doubles the
    cooldown window, capped at MAX_COOLDOWN_SECONDS. Returns the cooldown
    duration applied, in seconds.
    """
    strikes_key = _STRIKES_KEY.format(source=source)
    strikes = await redis.incr(strikes_key)
    await redis.expire(strikes_key, MAX_COOLDOWN_SECONDS)

    cooldown_seconds = min(base_seconds * (2 ** (strikes - 1)), MAX_COOLDOWN_SECONDS)
    await redis.set(_COOLDOWN_KEY.format(source=source), strikes, ex=cooldown_seconds)
    logger.warning("%s: strike %d — cooling down for %ds", source, strikes, cooldown_seconds)
    return cooldown_seconds


async def record_success(redis: ArqRedis, source: str) -> None:
    """Clear the strike count for `source` after a clean run."""
    await redis.delete(_STRIKES_KEY.format(source=source))
