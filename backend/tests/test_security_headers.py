from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.security import configure_basic_auth
from app.core.security_headers import configure_security_headers


def _app(**settings_overrides) -> FastAPI:
    app = FastAPI()

    @app.get("/thing")
    async def thing():
        return {"ok": True}

    configure_security_headers(app, Settings(**settings_overrides))
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_baseline_headers_are_present():
    async with _client(_app()) as client:
        response = await client.get("/thing")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"


async def test_the_default_csp_permits_what_the_built_spa_actually_loads():
    """The SPA loads its own hashed JS/CSS plus Google Fonts (see
    frontend/dist/index.html). A CSP that blocks those breaks the app, so the
    default is pinned here rather than left to be discovered in production."""
    async with _client(_app()) as client:
        response = await client.get("/thing")

    csp = response.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "https://fonts.googleapis.com" in csp
    assert "font-src 'self' https://fonts.gstatic.com" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


async def test_hsts_is_absent_in_development():
    """Sending HSTS over local HTTP would pin 127.0.0.1 to HTTPS in the
    browser and break every other local project on this machine."""
    async with _client(_app(environment="development")) as client:
        response = await client.get("/thing")

    assert "Strict-Transport-Security" not in response.headers


async def test_hsts_is_sent_outside_development():
    async with _client(_app(environment="production")) as client:
        response = await client.get("/thing")

    assert response.headers["Strict-Transport-Security"].startswith("max-age=31536000")


async def test_headers_can_be_disabled():
    async with _client(_app(security_headers_enabled=False)) as client:
        response = await client.get("/thing")

    assert "X-Content-Type-Options" not in response.headers


async def test_a_custom_csp_replaces_the_default():
    async with _client(_app(content_security_policy="default-src 'none'")) as client:
        response = await client.get("/thing")

    assert response.headers["Content-Security-Policy"] == "default-src 'none'"


async def test_an_unauthenticated_401_still_carries_the_headers():
    """Registration order matters: headers sit outside the auth middleware, so
    a short-circuited 401 passes back through them."""
    app = FastAPI()

    @app.get("/leads")
    async def leads():
        return {"items": []}

    settings = Settings(basic_auth_user="operator", basic_auth_password="a-long-enough-password")
    configure_basic_auth(app, settings)
    configure_security_headers(app, settings)

    async with _client(app) as client:
        response = await client.get("/leads")

    assert response.status_code == 401
    assert response.headers["X-Content-Type-Options"] == "nosniff"
