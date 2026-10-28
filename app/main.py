import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.core.redis import redis_client
from app.models import AnalyticsEvent, Comment, Follow, Like, MediaAsset, Notification, Post, User  # noqa: F401 - register models with SQLAlchemy metadata
from app.services.notification_worker import run_notification_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenient for local development. Use Alembic migrations in deployed environments.
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
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
app.include_router(api_router, prefix="/api/v1")
app.mount(
    "/media",
    StaticFiles(directory=settings.media_dir, check_dir=False),
    name="media",
)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
