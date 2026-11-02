import hashlib
import logging
from collections.abc import Iterable

from redis.exceptions import RedisError

from app.core.redis import redis_client

logger = logging.getLogger(__name__)


def feed_cache_key(
    user_id: int,
    author_ids: Iterable[int],
    limit: int,
    offset: int,
) -> str | None:
    author_ids = sorted(set(author_ids))
    version_keys = [
        f"posts:feed:membership-version:{user_id}",
        *(f"posts:feed:author-version:{author_id}" for author_id in author_ids),
    ]
    try:
        versions = redis_client.mget(version_keys)
    except RedisError:
        logger.warning("Redis feed-cache version lookup failed for user %s", user_id, exc_info=True)
        return None

    membership_version, *author_versions = versions
    snapshot = ",".join(
        [
            f"user:{user_id}:{membership_version or '0'}",
            *(
                f"author:{author_id}:{version or '0'}"
                for author_id, version in zip(author_ids, author_versions, strict=True)
            ),
        ]
    )
    version_hash = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()[:16]
    return f"posts:feed:v3:{user_id}:{limit}:{offset}:{version_hash}"


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


def discard_cached_feed(key: str) -> None:
    try:
        redis_client.delete(key)
    except RedisError:
        logger.warning("Could not discard invalid cached feed %s", key, exc_info=True)


def bump_author_feed_version(author_id: int) -> None:
    try:
        redis_client.incr(f"posts:feed:author-version:{author_id}")
    except RedisError:
        logger.warning(
            "Could not bump feed version for author %s; cached feeds may remain stale "
            "until their TTL expires",
            author_id,
            exc_info=True,
        )


def bump_membership_feed_version(user_id: int) -> None:
    try:
        redis_client.incr(f"posts:feed:membership-version:{user_id}")
    except RedisError:
        logger.warning(
            "Could not bump feed membership version for user %s; cached feeds may remain "
            "stale until their TTL expires",
            user_id,
            exc_info=True,
        )
