import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from redis.exceptions import RedisError

from app.core.config import Settings, effective_cors_origins, get_settings
from app.core.error_handlers import register_error_handlers
from app.core.security import configure_basic_auth
from app.core.security_headers import configure_security_headers
from app.routes import activities, dashboard, discovery, health, leads, outreach, outreach_drafts
from app.workers.queue import get_arq_pool
from app.workers.supervisor import WorkerSupervisor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # In "db" dispatch mode this process doesn't own the queue: it hands jobs
    # over through the DiscoveryJob table and a separate dispatcher enqueues
    # them elsewhere (see app/workers/dispatcher.py). There is no Redis to
    # connect to and no worker to supervise, so both are skipped outright
    # rather than failed and logged as errors on every start.
    if settings.dispatch_mode == "db":
        app.state.arq_redis = None
        logger.info("Dispatch mode is 'db' — this process will not connect to Redis or run a worker")
        yield
        return

    # A Redis outage at startup must not take down the whole API — /health,
    # /leads, /docs etc. don't need it. Only discovery-queueing endpoints do,
    # and they check app.state.arq_redis themselves and fail per-request.
    try:
        app.state.arq_redis = await get_arq_pool()
    except (RedisError, OSError, ConnectionError) as exc:
        logger.error("Could not connect to Redis at startup — queue endpoints will be unavailable: %s", exc)
        app.state.arq_redis = None

    worker_supervisor = WorkerSupervisor()
    if settings.auto_start_arq_worker:
        if app.state.arq_redis is not None:
            try:
                await worker_supervisor.start()
            except OSError as exc:
                logger.error("Could not start ARQ worker subprocess: %s", exc)
        else:
            logger.warning("Skipping ARQ worker auto-start — Redis is unavailable")

    try:
        yield
    finally:
        await worker_supervisor.stop()
        if app.state.arq_redis is not None:
            await app.state.arq_redis.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Order matters: Starlette runs the *last* registered middleware outermost, so
# CORS must be added after auth. That way a cross-origin preflight is answered
# by CORSMiddleware before it ever reaches the 401 check, and error responses
# still carry CORS headers instead of surfacing in the browser as opaque
# network failures.
#
# For the same reason, security headers are registered *after* auth and so sit
# outside it: the auth middleware short-circuits a 401 without calling inward,
# and a response that never reaches the headers middleware never gets them.
configure_basic_auth(app, settings)
configure_security_headers(app, settings)

app.add_middleware(
    CORSMiddleware,
    allow_origins=effective_cors_origins(settings),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)


app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(discovery.router)
app.include_router(leads.router)
app.include_router(outreach.router)
app.include_router(activities.router)
app.include_router(outreach_drafts.router)


def mount_frontend(app: FastAPI, settings: Settings) -> None:
    """Serve the built SPA from this app when a build is present.

    Mounted at "/" after every router, so API routes always win — a mount is a
    catch-all and would otherwise shadow them. A missing directory is the
    normal local-development case (Vite serves the frontend itself) and leaves
    the API untouched. In production this makes the SPA same-origin with the
    API, which is what removes CORS from the picture entirely.
    """
    dist_dir = Path(settings.frontend_dist_dir)
    if not dist_dir.is_dir():
        logger.info("No frontend build at %s — serving the API only", dist_dir)
        return

    app.mount("/", StaticFiles(directory=dist_dir, html=True), name="frontend")
    logger.info("Serving frontend from %s", dist_dir)


mount_frontend(app, settings)
