import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.authz import PERMISSION_REQUIREMENT_ATTR, get_principal, require
from app.core.permissions import Permission, Role, permissions_for
from app.core.error_handlers import register_error_handlers
from app.core.principal import Principal


# ---- the role → permission map --------------------------------------------


def test_owner_holds_every_permission():
    assert permissions_for(Role.OWNER) == frozenset(Permission)


def test_operator_holds_everything_except_the_deletes():
    operator = permissions_for(Role.OPERATOR)
    assert Permission.LEADS_DELETE not in operator
    assert Permission.DRAFTS_DELETE not in operator
    assert Permission.LEADS_WRITE in operator
    assert Permission.DISCOVERY_START in operator
    assert operator == frozenset(Permission) - {Permission.LEADS_DELETE, Permission.DRAFTS_DELETE}


def test_viewer_holds_reads_only():
    viewer = permissions_for(Role.VIEWER)
    assert Permission.LEADS_READ in viewer
    assert Permission.DASHBOARD_READ in viewer
    for write_permission in (
        Permission.LEADS_WRITE,
        Permission.LEADS_DELETE,
        Permission.PIPELINE_WRITE,
        Permission.ACTIVITIES_WRITE,
        Permission.AUDIT_RUN,
        Permission.OUTREACH_GENERATE,
        Permission.DRAFTS_WRITE,
        Permission.DRAFTS_DELETE,
        Permission.DISCOVERY_START,
        Permission.DISCOVERY_STOP,
        # Gates POST /leads/{id}/chat, which spends Groq quota and writes
        # chat rows — a read-only role must not hold it. Regression for
        # SecurityIssues.md M-3.
        Permission.ASSISTANT_USE,
    ):
        assert write_permission not in viewer, write_permission


def test_every_permission_is_granted_by_at_least_one_role():
    """A permission no role can hold would silently make its endpoint dead."""
    granted = frozenset().union(*(permissions_for(role) for role in Role))
    assert granted == frozenset(Permission)


def test_unknown_role_grants_nothing():
    assert permissions_for("not-a-role") == frozenset()  # type: ignore[arg-type]


# ---- Principal -------------------------------------------------------------


def test_principal_for_role_materializes_its_permissions():
    principal = Principal.for_role("someone", Role.VIEWER)
    assert principal.subject == "someone"
    assert principal.has(Permission.LEADS_READ)
    assert not principal.has(Permission.LEADS_WRITE)


def test_principal_is_immutable():
    principal = Principal.for_role("someone", Role.VIEWER)
    with pytest.raises(Exception):
        principal.subject = "someone-else"  # type: ignore[misc]


# ---- the require() dependency ---------------------------------------------


def _app_requiring(*permissions: Permission, role: Role) -> FastAPI:
    app = FastAPI()

    @app.get("/thing", dependencies=[Depends(require(*permissions))])
    async def thing():
        return {"ok": True}

    register_error_handlers(app)
    app.dependency_overrides[get_principal] = lambda: Principal.for_role("tester", role)
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_request_is_allowed_when_the_permission_is_held():
    async with _client(_app_requiring(Permission.LEADS_READ, role=Role.VIEWER)) as client:
        response = await client.get("/thing")
    assert response.status_code == 200


async def test_request_is_denied_when_the_permission_is_missing():
    async with _client(_app_requiring(Permission.LEADS_DELETE, role=Role.VIEWER)) as client:
        response = await client.get("/thing")

    assert response.status_code == 403
    body = response.json()["error"]
    assert body["code"] == "forbidden"
    assert body["retryable"] is False
    assert body["details"]["required"] == [Permission.LEADS_DELETE.value]


async def test_all_listed_permissions_must_be_held():
    app = _app_requiring(Permission.LEADS_READ, Permission.LEADS_DELETE, role=Role.OPERATOR)
    async with _client(app) as client:
        response = await client.get("/thing")

    assert response.status_code == 403
    assert response.json()["error"]["details"]["required"] == [Permission.LEADS_DELETE.value]


def test_require_rejects_an_empty_permission_list():
    """A guard that asserts nothing is worse than no guard — it looks protected."""
    with pytest.raises(ValueError):
        require()


def test_require_tags_its_dependency_for_the_route_coverage_test():
    dependency = require(Permission.LEADS_READ)
    assert getattr(dependency, PERMISSION_REQUIREMENT_ATTR) == (Permission.LEADS_READ,)
