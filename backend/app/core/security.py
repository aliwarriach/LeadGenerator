import base64
import binascii
import logging
import secrets
import time
from dataclasses import dataclass

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import Settings
from app.core.principal import AuthAccount, Principal
from app.schemas.errors import ErrorDetail

logger = logging.getLogger(__name__)

# The platform health check calls this without credentials, so guarding it
# would make a correctly-secured revision look unhealthy and fail to deploy.
# It exposes only "the database is reachable", which is not sensitive.
_UNPROTECTED_PATHS = frozenset({"/health"})

# Without this header a browser shows a blank 401 instead of a login prompt.
_CHALLENGE_HEADERS = {"WWW-Authenticate": 'Basic realm="Lead Generator", charset="UTF-8"'}


@dataclass
class _ThrottleState:
    failures: int = 0
    locked_until: float = 0.0


class _LoginThrottle:
    """In-process exponential backoff on failed Basic-auth attempts, keyed
    independently by source IP and by attempted username.

    Nothing slowed a credential attack against this app's sole perimeter
    control before this — see SecurityIssues.md M-4. In-process is adequate
    at today's single-instance scale; move to Redis-backed if the API ever
    scales past one instance. `_FREE_ATTEMPTS` tolerates the ordinary
    "typo'd password, tried again" case without locking anyone out —
    backoff only kicks in once a run of failures looks automated.
    """

    _FREE_ATTEMPTS = 5
    _BASE_DELAY_SECONDS = 1.0
    _MAX_DELAY_SECONDS = 60.0
    # Bounds memory under a sustained distributed attack: once full, new keys
    # are simply not tracked rather than growing the table without limit —
    # degrades back to "no throttle" for the newest attackers, not an OOM.
    _MAX_TRACKED_KEYS = 10_000

    def __init__(self) -> None:
        self._state: dict[str, _ThrottleState] = {}

    def seconds_until_unlocked(self, key: str) -> float | None:
        state = self._state.get(key)
        if state is None:
            return None
        remaining = state.locked_until - time.monotonic()
        return remaining if remaining > 0 else None

    def record_failure(self, key: str) -> None:
        state = self._state.get(key)
        if state is None:
            if len(self._state) >= self._MAX_TRACKED_KEYS:
                return
            state = self._state[key] = _ThrottleState()

        state.failures += 1
        if state.failures > self._FREE_ATTEMPTS:
            exponent = state.failures - self._FREE_ATTEMPTS - 1
            delay = min(self._BASE_DELAY_SECONDS * (2**exponent), self._MAX_DELAY_SECONDS)
            state.locked_until = time.monotonic() + delay

    def record_success(self, key: str) -> None:
        self._state.pop(key, None)


class InsecureConfigurationError(RuntimeError):
    """Raised at startup when a non-development environment has no credentials.

    Failing to boot is deliberate: the alternative — the previous behavior —
    was to log a warning and serve every endpoint publicly, which looks like a
    healthy deployment while being completely open.
    """


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic auth over every route except `_UNPROTECTED_PATHS`.

    Basic rather than a login screen: this app serves its own SPA, so the
    browser renders the credential prompt natively and the frontend needs no
    auth UI at all. On success the matched account's `Principal` is attached to
    `request.state` — `app.core.authz.get_principal` reads it from there, and
    per-route `require(...)` dependencies do the actual authorization.
    """

    def __init__(self, app, *, accounts: list[AuthAccount]) -> None:
        super().__init__(app)
        if not accounts:
            raise ValueError("BasicAuthMiddleware requires at least one account")
        self._accounts = tuple(accounts)
        self._throttle = _LoginThrottle()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _UNPROTECTED_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        attempted_username = _attempted_username(request.headers.get("Authorization"))

        for key in (client_ip, attempted_username):
            if key is None:
                continue
            retry_after = self._throttle.seconds_until_unlocked(key)
            if retry_after is not None:
                logger.warning(
                    "Authentication throttled for %r from %s — %.0fs remaining", attempted_username, client_ip, retry_after
                )
                error = ErrorDetail(
                    code="too_many_attempts",
                    message="Too many failed login attempts — try again shortly",
                    retryable=True,
                    retry_after_seconds=int(retry_after) + 1,
                )
                return JSONResponse(
                    status_code=429,
                    content={"error": error.model_dump()},
                    headers={"Retry-After": str(int(retry_after) + 1)},
                )

        account = self._authenticate(request.headers.get("Authorization"))
        if account is None:
            self._throttle.record_failure(client_ip)
            if attempted_username is not None:
                self._throttle.record_failure(attempted_username)
            logger.warning("Authentication failed for %r from %s", attempted_username, client_ip)

            error = ErrorDetail(
                code="unauthorized", message="Valid credentials are required", retryable=False
            )
            return JSONResponse(
                status_code=401, content={"error": error.model_dump()}, headers=_CHALLENGE_HEADERS
            )

        self._throttle.record_success(client_ip)
        self._throttle.record_success(account.username)
        logger.info("Authentication succeeded for %r (role=%s) from %s", account.username, account.role.value, client_ip)

        request.state.principal = Principal.for_role(account.username, account.role)
        return await call_next(request)

    def _authenticate(self, header: str | None) -> AuthAccount | None:
        credentials = _decode_basic_credentials(header)
        if credentials is None:
            return None

        username, password = credentials

        # Every account is compared, and both halves of each are compared, with
        # no early exit: short-circuiting would leak — via response timing —
        # which usernames exist and how many accounts are configured.
        matched: AuthAccount | None = None
        for account in self._accounts:
            username_ok = secrets.compare_digest(username, account.username)
            password_ok = secrets.compare_digest(password, account.password)
            if username_ok and password_ok:
                matched = account
        return matched


def _decode_basic_credentials(header: str | None) -> tuple[str, str] | None:
    """`(username, password)` from an Authorization header, or None if the
    header is absent, not Basic, or malformed. A malformed header is a client
    error and is indistinguishable here from a wrong password — both 401."""
    if not header:
        return None

    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded:
        return None

    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, ValueError):
        return None

    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return username, password


def _attempted_username(header: str | None) -> str | None:
    """The username half of `header`, for logging/throttling only — never
    the password. None if the header doesn't parse far enough to have one."""
    credentials = _decode_basic_credentials(header)
    return credentials[0] if credentials is not None else None


def build_auth_accounts(settings: Settings) -> list[AuthAccount]:
    """Every configured credential: the primary BASIC_AUTH_* pair (when both
    halves are set) followed by AUTH_ACCOUNTS entries.

    Duplicate usernames are dropped, first definition winning, so a typo'd
    extra account can never silently shadow the primary credential's role.
    """
    accounts: list[AuthAccount] = []
    if settings.basic_auth_user and settings.basic_auth_password:
        accounts.append(
            AuthAccount(
                username=settings.basic_auth_user,
                password=settings.basic_auth_password,
                role=settings.basic_auth_role,
            )
        )

    seen = {account.username for account in accounts}
    for account in settings.auth_accounts:
        if account.username in seen:
            logger.warning(
                "Ignoring duplicate AUTH_ACCOUNTS entry for username %r — the first definition wins",
                account.username,
            )
            continue
        seen.add(account.username)
        accounts.append(account)

    return accounts


def _warn_on_weak_passwords(accounts: list[AuthAccount], settings: Settings) -> None:
    minimum = settings.min_auth_password_length
    for account in accounts:
        if len(account.password) < minimum:
            logger.warning(
                "Password for account %r is shorter than %d characters — "
                "this is the only thing standing between the internet and every endpoint",
                account.username,
                minimum,
            )


def configure_basic_auth(app: FastAPI, settings: Settings) -> None:
    """Install Basic auth, or refuse to start if that would leave a deployed
    environment open.

    Unconfigured stays legal in `development` — it's what keeps local dev and
    the test suite unauthenticated. Anywhere else it is a misconfiguration that
    publishes the whole CRM, so it raises instead of logging and continuing.
    """
    accounts = build_auth_accounts(settings)

    if not accounts:
        if settings.environment != "development":
            raise InsecureConfigurationError(
                f"No credentials configured in environment {settings.environment!r}. "
                "Set BASIC_AUTH_USER and BASIC_AUTH_PASSWORD (or AUTH_ACCOUNTS) — "
                "refusing to start with every endpoint publicly accessible."
            )
        logger.info("No credentials configured — running unauthenticated (development only)")
        return

    _warn_on_weak_passwords(accounts, settings)
    app.add_middleware(BasicAuthMiddleware, accounts=accounts)
    logger.info(
        "Basic auth enabled for %d account(s): %s",
        len(accounts),
        ", ".join(f"{a.username}({a.role.value})" for a in accounts),
    )
