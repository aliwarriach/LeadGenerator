import base64

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

import pytest

from app.core.config import Settings
from app.core.permissions import Permission, Role
from app.core.principal import AuthAccount, Principal
from app.core.authz import get_principal, require
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.security import (
    BasicAuthMiddleware,
    InsecureConfigurationError,
    build_auth_accounts,
    configure_basic_auth,
)

_USER = "operator"
_PASSWORD = "s3cret-p@ss"


def _app(**settings_overrides) -> FastAPI:
    """A minimal app wired the same way main.py wires the real one."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/leads")
    async def leads(principal: Principal = Depends(get_principal)):
        return {"subject": principal.subject, "role": principal.role.value}

    settings = Settings(**settings_overrides)
    register_error_handlers(app)
    # get_principal resolves settings through Depends(get_settings), which
    # returns the process-wide cached instance — not the one built here. The
    # override is what makes per-test settings actually reach the dependency.
    app.dependency_overrides[get_settings] = lambda: settings
    configure_basic_auth(app, settings)
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _basic(username: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def _configured_app() -> FastAPI:
    return _app(basic_auth_user=_USER, basic_auth_password=_PASSWORD)


async def test_unconfigured_credentials_leave_the_app_open():
    """The default — what keeps local development and the rest of the suite
    unauthenticated."""
    app = _app()

    assert not any(m.cls is BasicAuthMiddleware for m in app.user_middleware)

    async with _client(app) as client:
        response = await client.get("/leads")

    assert response.status_code == 200


async def test_partially_configured_credentials_do_not_enable_auth():
    app = _app(basic_auth_user=_USER)

    async with _client(app) as client:
        response = await client.get("/leads")

    assert response.status_code == 200


async def test_missing_credentials_are_rejected_with_a_browser_challenge():
    async with _client(_configured_app()) as client:
        response = await client.get("/leads")

    assert response.status_code == 401
    # Without this header a browser renders a blank page instead of prompting.
    assert response.headers["WWW-Authenticate"].startswith("Basic realm=")
    assert response.json()["error"]["code"] == "unauthorized"


async def test_correct_credentials_are_accepted():
    async with _client(_configured_app()) as client:
        response = await client.get("/leads", headers=_basic(_USER, _PASSWORD))

    assert response.status_code == 200


async def test_wrong_password_is_rejected():
    async with _client(_configured_app()) as client:
        response = await client.get("/leads", headers=_basic(_USER, "wrong"))

    assert response.status_code == 401


async def test_wrong_username_is_rejected():
    async with _client(_configured_app()) as client:
        response = await client.get("/leads", headers=_basic("someone-else", _PASSWORD))

    assert response.status_code == 401


async def test_malformed_authorization_headers_are_rejected():
    app = _configured_app()

    async with _client(app) as client:
        for header in (
            {"Authorization": "Basic"},
            {"Authorization": "Basic !!!not-base64!!!"},
            {"Authorization": f"Bearer {base64.b64encode(b'operator:s3cret-p@ss').decode()}"},
            # Valid base64, but no ":" separator to split on.
            {"Authorization": f"Basic {base64.b64encode(b'no-separator').decode()}"},
        ):
            response = await client.get("/leads", headers=header)
            assert response.status_code == 401, header


async def test_health_stays_open_so_platform_probes_do_not_break():
    async with _client(_configured_app()) as client:
        response = await client.get("/health")

    assert response.status_code == 200


# ---- roles carried by credentials -----------------------------------------


async def test_the_primary_credential_carries_its_configured_role():
    app = _app(basic_auth_user=_USER, basic_auth_password=_PASSWORD, basic_auth_role=Role.OPERATOR)

    async with _client(app) as client:
        response = await client.get("/leads", headers=_basic(_USER, _PASSWORD))

    assert response.json() == {"subject": _USER, "role": "operator"}


async def test_additional_accounts_authenticate_with_their_own_roles():
    app = _app(
        basic_auth_user=_USER,
        basic_auth_password=_PASSWORD,
        auth_accounts=[AuthAccount(username="analyst", password="read-only-pass", role=Role.VIEWER)],
    )

    async with _client(app) as client:
        owner = await client.get("/leads", headers=_basic(_USER, _PASSWORD))
        analyst = await client.get("/leads", headers=_basic("analyst", "read-only-pass"))
        crossed = await client.get("/leads", headers=_basic("analyst", _PASSWORD))

    assert owner.json()["role"] == "owner"
    assert analyst.json()["role"] == "viewer"
    # Credentials must not be interchangeable across accounts.
    assert crossed.status_code == 401


async def test_an_account_can_be_configured_without_the_primary_credential():
    app = _app(auth_accounts=[AuthAccount(username="solo", password="only-account", role=Role.OPERATOR)])

    async with _client(app) as client:
        assert (await client.get("/leads")).status_code == 401
        response = await client.get("/leads", headers=_basic("solo", "only-account"))

    assert response.json()["role"] == "operator"


def test_a_duplicate_username_cannot_shadow_the_primary_credentials_role():
    settings = Settings(
        basic_auth_user=_USER,
        basic_auth_password=_PASSWORD,
        basic_auth_role=Role.OWNER,
        auth_accounts=[AuthAccount(username=_USER, password="other", role=Role.VIEWER)],
    )

    accounts = build_auth_accounts(settings)

    assert [(a.username, a.role) for a in accounts] == [(_USER, Role.OWNER)]


# ---- unauthenticated (development) principal -------------------------------


async def test_unconfigured_auth_yields_the_configured_unauthenticated_role():
    async with _client(_app()) as client:
        response = await client.get("/leads")

    assert response.json() == {"subject": "unauthenticated", "role": "owner"}


async def test_the_unauthenticated_role_can_be_downgraded_for_local_testing():
    async with _client(_app(unauthenticated_role=Role.VIEWER)) as client:
        response = await client.get("/leads")

    assert response.json()["role"] == "viewer"


# ---- fail closed -----------------------------------------------------------


@pytest.mark.parametrize("environment", ["production", "staging"])
def test_a_deployed_environment_refuses_to_start_without_credentials(environment):
    """Previously this only logged a warning and served every endpoint
    publicly — a misconfiguration that looks like a healthy deployment."""
    with pytest.raises(InsecureConfigurationError):
        configure_basic_auth(FastAPI(), Settings(environment=environment))


def test_a_deployed_environment_starts_when_credentials_are_configured():
    app = FastAPI()
    configure_basic_auth(
        app, Settings(environment="production", basic_auth_user=_USER, basic_auth_password=_PASSWORD)
    )
    assert any(m.cls is BasicAuthMiddleware for m in app.user_middleware)


def test_development_still_starts_unauthenticated():
    app = FastAPI()
    configure_basic_auth(app, Settings(environment="development"))
    assert not any(m.cls is BasicAuthMiddleware for m in app.user_middleware)


def test_a_short_password_warns_but_does_not_block_startup(caplog):
    app = FastAPI()
    with caplog.at_level("WARNING"):
        configure_basic_auth(
            app, Settings(environment="production", basic_auth_user=_USER, basic_auth_password="short")
        )

    assert any("shorter than" in record.message for record in caplog.records)
    assert any(m.cls is BasicAuthMiddleware for m in app.user_middleware)


async def test_permissions_are_enforced_against_the_authenticated_role():
    """End to end: credential → role → permission check on a real route."""
    app = FastAPI()

    @app.get("/leads", dependencies=[Depends(require(Permission.LEADS_DELETE))])
    async def delete_capable():
        return {"ok": True}

    settings = Settings(
        auth_accounts=[
            AuthAccount(username="owner", password="owner-pass", role=Role.OWNER),
            AuthAccount(username="analyst", password="analyst-pass", role=Role.VIEWER),
        ]
    )
    register_error_handlers(app)
    app.dependency_overrides[get_settings] = lambda: settings
    configure_basic_auth(app, settings)

    async with _client(app) as client:
        allowed = await client.get("/leads", headers=_basic("owner", "owner-pass"))
        denied = await client.get("/leads", headers=_basic("analyst", "analyst-pass"))

    assert allowed.status_code == 200
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "forbidden"
