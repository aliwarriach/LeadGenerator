import base64
import binascii
import logging
import secrets

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.schemas.errors import ErrorDetail

logger = logging.getLogger(__name__)

# The platform health check calls this without credentials, so guarding it
# would make a correctly-secured revision look unhealthy and fail to deploy.
# It exposes only "the database is reachable", which is not sensitive.
_UNPROTECTED_PATHS = frozenset({"/health"})

# Without this header a browser shows a blank 401 instead of a login prompt.
_CHALLENGE_HEADERS = {"WWW-Authenticate": 'Basic realm="Lead Generator", charset="UTF-8"'}


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic auth over every route except `_UNPROTECTED_PATHS`.

    A single shared credential rather than a user model: this is a
    single-operator internal tool, and the platform-native alternative (IAM on
    the service itself) can't be satisfied by a browser calling the API from
    the SPA this same app serves. Basic auth also means the browser renders the
    prompt natively, so the frontend needs no login screen at all.
    """

    def __init__(self, app, *, username: str, password: str) -> None:
        super().__init__(app)
        self._username = username
        self._password = password

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _UNPROTECTED_PATHS:
            return await call_next(request)

        if not self._is_authorized(request.headers.get("Authorization")):
            error = ErrorDetail(
                code="unauthorized", message="Valid credentials are required", retryable=False
            )
            return JSONResponse(
                status_code=401, content={"error": error.model_dump()}, headers=_CHALLENGE_HEADERS
            )

        return await call_next(request)

    def _is_authorized(self, header: str | None) -> bool:
        if not header:
            return False

        scheme, _, encoded = header.partition(" ")
        if scheme.lower() != "basic" or not encoded:
            return False

        try:
            decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, ValueError):
            # Malformed base64 or non-UTF-8 payload — a client error, not a
            # server one, and indistinguishable from a wrong password here.
            return False

        username, separator, password = decoded.partition(":")
        if not separator:
            return False

        # Both halves are compared unconditionally: short-circuiting once the
        # username mismatched would leak, via response timing, which half was
        # wrong and let an attacker enumerate usernames.
        username_ok = secrets.compare_digest(username, self._username)
        password_ok = secrets.compare_digest(password, self._password)
        return username_ok and password_ok


def configure_basic_auth(app: FastAPI, settings: Settings) -> None:
    """Install Basic auth when credentials are configured, otherwise do nothing.

    Unconfigured is the default, which is what keeps local development and the
    test suite unauthenticated. Leaving a deployed environment open is almost
    certainly a misconfiguration rather than a choice, so that case is logged
    loudly instead of passing silently.
    """
    if not settings.basic_auth_user or not settings.basic_auth_password:
        if settings.environment != "development":
            logger.warning(
                "BASIC_AUTH_USER/BASIC_AUTH_PASSWORD are not set in environment %r — "
                "every endpoint is publicly accessible",
                settings.environment,
            )
        return

    app.add_middleware(
        BasicAuthMiddleware, username=settings.basic_auth_user, password=settings.basic_auth_password
    )
