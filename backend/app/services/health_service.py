import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import health_repository
from app.schemas.health import HealthStatus

logger = logging.getLogger(__name__)


class DatabaseUnavailableError(Exception):
    pass


async def check_health(session: AsyncSession) -> HealthStatus:
    try:
        await health_repository.ping_database(session)
    except Exception as exc:
        # Connection failures surface as raw driver/OS errors (e.g. ConnectionRefusedError),
        # not SQLAlchemyError, since SQLAlchemy only wraps errors after a connection exists.
        logger.error("Database health check failed", exc_info=exc)
        raise DatabaseUnavailableError("Database connection failed") from exc

    return HealthStatus(status="ok", database="connected")
