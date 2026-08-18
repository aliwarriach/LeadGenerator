"""Response hardening headers.

This app serves its own built SPA from the same origin as the API
(`main.mount_frontend`), so the browser-facing headers below are the app's
responsibility rather than a reverse proxy's.
"""

import logging

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings

logger = logging.getLogger(__name__)

# One year, the value browsers require before a host is eligible for HSTS
# preloading. Not preloaded here — no `preload` directive — because that is an
# irreversible commitment for the whole domain.
_HSTS_MAX_AGE_SECONDS = 31_536_000

_STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    # Redundant with the CSP's frame-ancestors for modern browsers, kept for
    # the ones that only honor the older header.
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Lead data and AI output are not something to hand to a third-party
    # translator/prefetch service.
    "X-Robots-Tag": "noindex, nofollow",
    # This app uses none of these browser APIs — denying them outright means
    # an XSS that got past the CSP still can't touch the camera/mic/location.
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, content_security_policy: str, enable_hsts: bool) -> None:
        super().__init__(app)
        self._csp = content_security_policy
        self._enable_hsts = enable_hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        # setdefault, not assignment: a route that deliberately sets its own
        # value (e.g. a future embeddable export) keeps it.
        for header, value in _STATIC_HEADERS.items():
            response.headers.setdefault(header, value)

        if self._csp:
            response.headers.setdefault("Content-Security-Policy", self._csp)

        # Only over TLS. Sending it in local HTTP development would pin
        # 127.0.0.1 to HTTPS in the browser and break every other local project
        # sharing that host.
        if self._enable_hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", f"max-age={_HSTS_MAX_AGE_SECONDS}; includeSubDomains"
            )

        return response


def configure_security_headers(app: FastAPI, settings: Settings) -> None:
    if not settings.security_headers_enabled:
        logger.warning("Security response headers are disabled by configuration")
        return

    app.add_middleware(
        SecurityHeadersMiddleware,
        content_security_policy=settings.content_security_policy,
        enable_hsts=settings.environment != "development",
    )
