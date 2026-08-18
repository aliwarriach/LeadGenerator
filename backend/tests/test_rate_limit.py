from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.authz import get_principal
from app.core.config import Settings, get_settings
from app.core.error_handlers import register_error_handlers
from app.core.permissions import Role
from app.core.principal import Principal
from app.core.rate_limit import _SlidingWindowLimiter, require_llm_quota


# ---- _SlidingWindowLimiter (pure unit, own instance per test) -------------


def test_allows_calls_under_the_limit():
    limiter = _SlidingWindowLimiter()
    for _ in range(3):
        assert limiter.seconds_until_allowed("subject", max_calls=3, window_seconds=3600) is None


def test_blocks_calls_over_the_limit():
    limiter = _SlidingWindowLimiter()
    for _ in range(3):
        limiter.seconds_until_allowed("subject", max_calls=3, window_seconds=3600)

    retry_after = limiter.seconds_until_allowed("subject", max_calls=3, window_seconds=3600)
    assert retry_after is not None
    assert retry_after > 0


def test_different_keys_have_independent_budgets():
    limiter = _SlidingWindowLimiter()
    for _ in range(3):
        limiter.seconds_until_allowed("alice", max_calls=3, window_seconds=3600)

    assert limiter.seconds_until_allowed("alice", max_calls=3, window_seconds=3600) is not None
    assert limiter.seconds_until_allowed("bob", max_calls=3, window_seconds=3600) is None


def test_old_calls_fall_out_of_the_window():
    limiter = _SlidingWindowLimiter()
    # A zero-width window means every prior call is immediately stale — the
    # cheapest way to exercise the eviction branch without sleeping in a test.
    for _ in range(5):
        assert limiter.seconds_until_allowed("subject", max_calls=1, window_seconds=0) is None


# ---- require_llm_quota dependency (fresh subject per test — the limiter is
# a module-level singleton shared with the real app's routes) ---------------


def _app_for(subject: str, *, max_calls: int) -> FastAPI:
    app = FastAPI()

    @app.get("/llm-thing", dependencies=[Depends(require_llm_quota)])
    async def thing():
        return {"ok": True}

    register_error_handlers(app)
    app.dependency_overrides[get_principal] = lambda: Principal.for_role(subject, Role.OWNER)
    app.dependency_overrides[get_settings] = lambda: Settings(llm_rate_limit_per_hour=max_calls)
    return app


def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_require_llm_quota_allows_calls_within_budget():
    app = _app_for("quota-test-allows", max_calls=2)

    async with _client(app) as client:
        first = await client.get("/llm-thing")
        second = await client.get("/llm-thing")

    assert first.status_code == 200
    assert second.status_code == 200


async def test_require_llm_quota_rejects_calls_over_budget():
    app = _app_for("quota-test-rejects", max_calls=1)

    async with _client(app) as client:
        allowed = await client.get("/llm-thing")
        denied = await client.get("/llm-thing")

    assert allowed.status_code == 200
    assert denied.status_code == 429
    body = denied.json()["error"]
    assert body["code"] == "rate_limited"
    assert body["retryable"] is True


async def test_require_llm_quota_tracks_budget_per_principal_subject():
    app = FastAPI()

    @app.get("/llm-thing", dependencies=[Depends(require_llm_quota)])
    async def thing():
        return {"ok": True}

    register_error_handlers(app)
    app.dependency_overrides[get_settings] = lambda: Settings(llm_rate_limit_per_hour=1)

    async def _run_as(subject: str) -> int:
        app.dependency_overrides[get_principal] = lambda: Principal.for_role(subject, Role.OWNER)
        async with _client(app) as client:
            response = await client.get("/llm-thing")
        return response.status_code

    assert await _run_as("quota-test-per-subject-a") == 200
    assert await _run_as("quota-test-per-subject-b") == 200
