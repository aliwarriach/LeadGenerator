import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.routes import activities, dashboard, discovery, health, leads, outreach, outreach_drafts
from app.schemas.errors import ApiError
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(ApiError)
async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.error.model_dump()})


app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(discovery.router)
app.include_router(leads.router)
app.include_router(outreach.router)
app.include_router(activities.router)
app.include_router(outreach_drafts.router)
