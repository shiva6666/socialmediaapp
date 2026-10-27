from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings
from app.core.database import Base, engine
from app.models import Comment, Follow, Like, MediaAsset, Notification, Post, User  # noqa: F401 - register models with SQLAlchemy metadata


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Convenient for local development. Use Alembic migrations in deployed environments.
    Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    yield


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
