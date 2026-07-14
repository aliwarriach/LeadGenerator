import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.routes import discovery, health, leads
from app.workers.queue import get_arq_pool

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

    try:
        yield
    finally:
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

app.include_router(health.router)
app.include_router(discovery.router)
app.include_router(leads.router)
