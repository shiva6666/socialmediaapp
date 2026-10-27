from fastapi import APIRouter

from app.api.routes import auth, follows, interactions, media, notifications, posts

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(posts.router, prefix="/posts", tags=["posts"])
api_router.include_router(follows.router, prefix="/users", tags=["follows"])
api_router.include_router(interactions.router, prefix="", tags=["interactions"])
api_router.include_router(media.router, prefix="", tags=["media"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
