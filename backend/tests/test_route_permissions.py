"""Guards the guard: every route must declare a permission.

The failure this prevents is a new endpoint shipping with no `require(...)`
dependency and therefore no authorization at all — which is exactly the state
the whole API was in before. Adding a route to `_INTENTIONALLY_UNPROTECTED`
is a deliberate, reviewable act; forgetting one is not.
"""

from fastapi.routing import APIRoute

from app.core.authz import PERMISSION_REQUIREMENT_ATTR
from app.core.permissions import Permission
from app.main import app

# Only the platform health probe, which is called without credentials and
# exposes nothing but "the database is reachable" (see app/core/security.py).
_INTENTIONALLY_UNPROTECTED: frozenset[tuple[str, str]] = frozenset({("GET", "/health")})


def _declared_permissions(route: APIRoute) -> tuple[Permission, ...]:
    """Permissions declared anywhere in a route's dependency tree."""
    found: list[Permission] = []
    pending = list(route.dependant.dependencies)
    while pending:
        dependant = pending.pop()
        permissions = getattr(dependant.call, PERMISSION_REQUIREMENT_ATTR, None)
        if permissions:
            found.extend(permissions)
        pending.extend(dependant.dependencies)
    return tuple(found)


def _api_routes() -> list[tuple[str, APIRoute]]:
    """Every application endpoint, as (method, route).

    Walks recursively. This FastAPI version does not flatten an included
    router onto `app.routes`; it stores a `_IncludedRouter` wrapper that
    reaches its endpoints through `original_router.routes`. A scan that only
    looks at `app.routes` finds zero endpoints — and a coverage test that
    finds nothing passes while protecting nothing, so both descents are
    handled explicitly.

    Paths are read straight off the `APIRoute`, which is correct because
    `main.py` includes each router without an extra prefix (the prefix lives
    on the router itself).

    Starlette's own `/docs`, `/redoc` and `/openapi.json` are not `APIRoute`s
    and are intentionally out of scope: framework endpoints, already behind
    the auth middleware, exposing only the API's shape.
    """
    pairs: list[tuple[str, APIRoute]] = []
    seen: set[int] = set()
    pending = list(app.routes)

    while pending:
        route = pending.pop()
        if id(route) in seen:
            continue
        seen.add(id(route))

        if isinstance(route, APIRoute):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                pairs.append((method, route))
            continue

        pending.extend(getattr(route, "routes", []))
        included = getattr(route, "original_router", None)
        if included is not None:
            pending.extend(included.routes)

    return pairs


def test_every_route_declares_a_permission_or_is_explicitly_exempt():
    unguarded = [
        f"{method} {route.path}"
        for method, route in _api_routes()
        if not _declared_permissions(route) and (method, route.path) not in _INTENTIONALLY_UNPROTECTED
    ]
    assert not unguarded, (
        "These routes have no permission requirement. Add "
        "dependencies=[Depends(require(Permission.X))], or add them to "
        f"_INTENTIONALLY_UNPROTECTED with a reason: {unguarded}"
    )


def test_the_exemption_list_has_not_grown_silently():
    """Every exempt entry must still be a real route — a stale exemption could
    otherwise mask a renamed endpoint going unguarded."""
    existing = {(method, route.path) for method, route in _api_routes()}
    assert _INTENTIONALLY_UNPROTECTED <= existing


def test_the_full_route_inventory_is_guarded_as_intended():
    """Pins the actual permission on each endpoint, so a wrong-but-present
    guard (e.g. a delete behind a read permission) fails too."""
    expected = {
        ("GET", "/dashboard/stats"): Permission.DASHBOARD_READ,
        ("GET", "/dashboard/discovery-volume"): Permission.DASHBOARD_READ,
        ("GET", "/dashboard/lead-stage-mix"): Permission.DASHBOARD_READ,
        ("GET", "/dashboard/activity"): Permission.DASHBOARD_READ,
        ("POST", "/start-discovery"): Permission.DISCOVERY_START,
        ("GET", "/discovery-runs"): Permission.DISCOVERY_READ,
        ("GET", "/discovery-runs/stats"): Permission.DISCOVERY_READ,
        ("GET", "/discovery-runs/{run_id}"): Permission.DISCOVERY_READ,
        ("POST", "/discovery-runs/{run_id}/stop"): Permission.DISCOVERY_STOP,
        ("GET", "/discovery-jobs"): Permission.DISCOVERY_READ,
        ("GET", "/discovery-jobs/{job_id}"): Permission.DISCOVERY_READ,
        ("POST", "/discovery-jobs/{job_id}/stop"): Permission.DISCOVERY_STOP,
        ("GET", "/discovery-jobs/{job_id}/events"): Permission.DISCOVERY_READ,
        ("GET", "/leads"): Permission.LEADS_READ,
        ("GET", "/leads/{lead_id}"): Permission.LEADS_READ,
        ("PATCH", "/leads/{lead_id}"): Permission.LEADS_WRITE,
        ("PATCH", "/leads/{lead_id}/stage"): Permission.PIPELINE_WRITE,
        ("POST", "/leads/{lead_id}/audit"): Permission.AUDIT_RUN,
        ("POST", "/leads/{lead_id}/chat"): Permission.ASSISTANT_USE,
        ("GET", "/leads/{lead_id}/chat"): Permission.LEADS_READ,
        ("POST", "/outreach/email/{lead_id}"): Permission.OUTREACH_GENERATE,
        ("POST", "/outreach/whatsapp/{lead_id}"): Permission.OUTREACH_GENERATE,
        ("POST", "/outreach/proposal/{lead_id}"): Permission.OUTREACH_GENERATE,
        ("POST", "/outreach-drafts/{lead_id}"): Permission.DRAFTS_WRITE,
        ("GET", "/outreach-drafts/{lead_id}"): Permission.DRAFTS_READ,
        ("PATCH", "/outreach-drafts/{draft_id}"): Permission.DRAFTS_WRITE,
        ("POST", "/outreach-drafts/{draft_id}/pdf"): Permission.DRAFTS_WRITE,
        ("GET", "/activities/{lead_id}"): Permission.ACTIVITIES_READ,
        ("POST", "/activities/{lead_id}"): Permission.ACTIVITIES_WRITE,
    }

    actual = {
        (method, route.path): _declared_permissions(route)
        for method, route in _api_routes()
        if (method, route.path) not in _INTENTIONALLY_UNPROTECTED
    }

    assert set(actual) == set(expected), "route inventory changed — update this test"
    for key, permission in expected.items():
        assert actual[key] == (permission,), f"{key} is guarded by {actual[key]}, expected {permission}"
