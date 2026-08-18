"""FastAPI wiring for authorization: resolve the caller, then gate the route.

Split from `app.core.principal` so that module stays importable by
`app.core.config` (which would otherwise be a cycle) and by non-HTTP callers
such as the future agent tool layer.
"""

import logging
from collections.abc import Callable

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.permissions import Permission
from app.core.principal import Principal
from app.schemas.errors import ApiError, ErrorDetail

logger = logging.getLogger(__name__)

# Marks a dependency produced by `require()`. `tests/test_route_permissions.py`
# walks every route's dependency tree looking for this, so a new endpoint that
# forgets to declare a permission fails the suite instead of shipping open.
PERMISSION_REQUIREMENT_ATTR = "__required_permissions__"

# Subject recorded when no credentials are configured at all — local dev and
# the test suite. Never appears in a deployed environment, because
# `configure_basic_auth` refuses to start one without credentials.
UNAUTHENTICATED_SUBJECT = "unauthenticated"


def get_principal(request: Request, settings: Settings = Depends(get_settings)) -> Principal:
    """The caller for this request.

    `BasicAuthMiddleware` puts a `Principal` on `request.state` when auth is
    configured. When it isn't — local development, tests — there is no
    credential to derive an identity from, so one is synthesized with
    `settings.unauthenticated_role` (owner by default, which is what keeps
    development and the existing suite working unchanged).
    """
    principal = getattr(request.state, "principal", None)
    if principal is not None:
        return principal
    return Principal.for_role(UNAUTHENTICATED_SUBJECT, settings.unauthenticated_role)


def require(*permissions: Permission) -> Callable[..., Principal]:
    """Route dependency asserting the caller holds every listed permission.

    Usage — as a route-level dependency when the body doesn't need the
    principal, which is the common case:

        @router.get("/leads", dependencies=[Depends(require(Permission.LEADS_READ))])
    """
    if not permissions:
        raise ValueError("require() needs at least one permission")

    def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        missing = [p for p in permissions if not principal.has(p)]
        if missing:
            # Logged at info, not warning: a 403 is a correct outcome for a
            # correctly-configured lower-privilege role, not an incident.
            logger.info(
                "Denied %s (role=%s) — missing %s",
                principal.subject,
                principal.role.value,
                ", ".join(p.value for p in missing),
            )
            raise ApiError(
                403,
                ErrorDetail(
                    code="forbidden",
                    message="You do not have permission to perform this action",
                    retryable=False,
                    details={"required": [p.value for p in missing]},
                ),
            )
        return principal

    setattr(_dependency, PERMISSION_REQUIREMENT_ATTR, tuple(permissions))
    return _dependency
