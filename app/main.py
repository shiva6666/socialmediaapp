import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from redis.exceptions import (
    ConnectionError as RedisConnectionError,
    RedisError,
    TimeoutError as RedisTimeoutError,
)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.rate_limit import limiter
from app.core.redis import redis_client
from app.models import AnalyticsEvent, Comment, Follow, Like, MediaAsset, Notification, Post, User  # noqa: F401 - register models with SQLAlchemy metadata
from app.services.notification_worker import run_notification_worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenient for local development; deployed environments should apply Alembic migrations.
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
    notification_worker = asyncio.create_task(run_notification_worker())
    try:
        yield
    finally:
        notification_worker.cancel()
        try:
            await notification_worker
        except asyncio.CancelledError:
            pass
        redis_client.close()


app = FastAPI(title="Insta Clone API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(RedisError)
def redis_unavailable(request: Request, error: RedisError) -> JSONResponse:
    logger.error(
        "Redis request failed for %s",
        request.url.path,
        exc_info=(type(error), error, error.__traceback__),
    )
    return JSONResponse(
        status_code=503,
        content={"detail": "A required service is temporarily unavailable"},
        headers={"Retry-After": "1"},
    )


app.add_exception_handler(RedisConnectionError, redis_unavailable)
app.add_exception_handler(RedisTimeoutError, redis_unavailable)


app.mount(
    "/media",
    StaticFiles(directory=settings.media_dir, check_dir=False),
    name="media",
)


@app.get("/health", tags=["health"])
def health_check(request: Request) -> dict[str, str]:
    return {"status": "ok"}
