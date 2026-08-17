import base64

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.security import BasicAuthMiddleware, configure_basic_auth

_USER = "operator"
_PASSWORD = "s3cret-p@ss"


def _app(**settings_overrides) -> FastAPI:
    """A minimal app wired the same way main.py wires the real one."""
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/leads")
    async def leads():
        return {"items": []}

    configure_basic_auth(app, Settings(**settings_overrides))
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
