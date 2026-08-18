"""In-process per-principal rate limiting for LLM-backed endpoints.

Every Groq-backed route (audit, chat, the three outreach generators) spends
real external quota per call with no other cost control in front of it — any
authenticated principal could loop one and run up the Groq bill or saturate
the worker pool. See SecurityIssues.md M-5.

A fixed-window counter per `principal.subject`, shared across all five
LLM-backed routes (they all draw on the same Groq quota). In-process is
adequate at today's single-instance scale — same trade-off already accepted
for the auth throttle in `app/core/security.py`; move to Redis-backed if the
API ever scales past one instance.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Depends

from app.core.authz import get_principal
from app.core.config import Settings, get_settings
from app.core.principal import Principal
from app.schemas.errors import ApiError, ErrorDetail

_WINDOW_SECONDS = 3600.0


class _SlidingWindowLimiter:
    def __init__(self) -> None:
        self._calls: dict[str, deque[float]] = defaultdict(deque)

    def seconds_until_allowed(self, key: str, *, max_calls: int, window_seconds: float) -> float | None:
        """None and records the call if `key` is under `max_calls` within the
        trailing `window_seconds`; otherwise the seconds until it isn't."""
        now = time.monotonic()
        calls = self._calls[key]
        while calls and now - calls[0] > window_seconds:
            calls.popleft()

        if len(calls) >= max_calls:
            return window_seconds - (now - calls[0])

        calls.append(now)
        return None


_llm_call_limiter = _SlidingWindowLimiter()


def require_llm_quota(
    principal: Principal = Depends(get_principal), settings: Settings = Depends(get_settings)
) -> Principal:
    """Route dependency: caps how many LLM-backed calls one principal can
    make per rolling hour, across every Groq-backed endpoint combined."""
    retry_after = _llm_call_limiter.seconds_until_allowed(
        principal.subject, max_calls=settings.llm_rate_limit_per_hour, window_seconds=_WINDOW_SECONDS
    )
    if retry_after is not None:
        raise ApiError(
            429,
            ErrorDetail(
                code="rate_limited",
                message="AI request limit reached for this account — try again later",
                retryable=True,
                retry_after_seconds=int(retry_after) + 1,
            ),
        )
    return principal
