import logging
from typing import Literal

from fastapi import BackgroundTasks
from redis.exceptions import RedisError

from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.models.notification import Notification

logger = logging.getLogger(__name__)
NOTIFICATION_STREAM = "notifications"
NOTIFICATION_CONSUMER_GROUP = "notification-writers"


def queue_notification(
    background_tasks: BackgroundTasks,
    recipient_id: int,
    actor_id: int,
    event_type: Literal["follow", "like", "comment"],
    post_id: int | None = None,
) -> None:
    if recipient_id == actor_id:
        return

    background_tasks.add_task(
        enqueue_notification,
        recipient_id,
        actor_id,
        event_type,
        post_id,
    )


def enqueue_notification(
    recipient_id: int,
    actor_id: int,
    event_type: Literal["follow", "like", "comment"],
    post_id: int | None,
) -> None:
    fields = {
        "recipient_id": str(recipient_id),
        "actor_id": str(actor_id),
        "event_type": event_type,
        "post_id": str(post_id) if post_id is not None else "",
    }
    try:
        redis_client.xadd(NOTIFICATION_STREAM, fields)
    except RedisError:
        logger.exception("Could not enqueue notification; attempting direct database write")
        try:
            persist_notification(fields)
        except Exception:
            logger.exception("Direct notification persistence also failed")


def persist_notification(fields: dict[str, str]) -> None:
    with SessionLocal() as db:
        db.add(
            Notification(
                recipient_id=int(fields["recipient_id"]),
                actor_id=int(fields["actor_id"]),
                event_type=fields["event_type"],
                post_id=int(fields["post_id"]) if fields["post_id"] else None,
            )
        )
        db.commit()
