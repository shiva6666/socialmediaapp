import logging
from collections.abc import Iterable

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis import redis_client
from app.models.follow import Follow

logger = logging.getLogger(__name__)


def feed_cache_key(user_id: int, limit: int, offset: int) -> str:
    return f"posts:feed:{user_id}:{limit}:{offset}"


def get_cached_feed(key: str) -> str | None:
    try:
        return redis_client.get(key)
    except RedisError:
        logger.warning("Redis feed-cache read failed for key %s", key, exc_info=True)
        return None


def cache_feed(key: str, value: str, ttl_seconds: int) -> None:
    try:
        redis_client.setex(key, ttl_seconds, value)
    except RedisError:
        logger.warning("Redis feed-cache write failed for key %s", key, exc_info=True)


def invalidate_feed_cache(user_ids: Iterable[int]) -> None:
    try:
        for user_id in set(user_ids):
            pattern = f"posts:feed:{user_id}:*"
            keys = list(redis_client.scan_iter(match=pattern))
            if keys:
                redis_client.delete(*keys)
    except RedisError:
        logger.warning("Redis feed-cache invalidation failed", exc_info=True)


def invalidate_author_feeds(db: Session, author_id: int) -> None:
    follower_ids = db.scalars(
        select(Follow.follower_id).where(Follow.following_id == author_id)
    ).all()
    invalidate_feed_cache([author_id, *follower_ids])
