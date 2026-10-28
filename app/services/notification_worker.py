import asyncio
import logging
import socket
from uuid import uuid4

from redis.exceptions import RedisError, ResponseError
from sqlalchemy.exc import IntegrityError

from app.core.redis import redis_client
from app.services.notifications import (
    NOTIFICATION_CONSUMER_GROUP,
    NOTIFICATION_STREAM,
    persist_notification,
)

logger = logging.getLogger(__name__)


def ensure_consumer_group() -> None:
    try:
        redis_client.xgroup_create(
            NOTIFICATION_STREAM,
            NOTIFICATION_CONSUMER_GROUP,
            id="0",
            mkstream=True,
        )
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise


def claim_pending_notifications(consumer_name: str):
    return redis_client.xautoclaim(
        NOTIFICATION_STREAM,
        NOTIFICATION_CONSUMER_GROUP,
        consumer_name,
        min_idle_time=30_000,
        start_id="0-0",
        count=10,
    )


async def run_notification_worker() -> None:
    consumer_name = f"{socket.gethostname()}-{uuid4().hex}"
    group_ready = False

    while True:
        try:
            if not group_ready:
                await asyncio.to_thread(ensure_consumer_group)
                group_ready = True

            _, pending, _ = await asyncio.to_thread(claim_pending_notifications, consumer_name)
            if pending:
                records = [(NOTIFICATION_STREAM, pending)]
            else:
                records = await asyncio.to_thread(
                    redis_client.xreadgroup,
                    NOTIFICATION_CONSUMER_GROUP,
                    consumer_name,
                    {NOTIFICATION_STREAM: ">"},
                    count=10,
                    block=1000,
                )

            for stream, messages in records:
                for message_id, fields in messages:
                    try:
                        await asyncio.to_thread(persist_notification, fields)
                        await asyncio.to_thread(
                            redis_client.xack,
                            stream,
                            NOTIFICATION_CONSUMER_GROUP,
                            message_id,
                        )
                    except IntegrityError:
                        logger.error(
                            "Discarding notification %s because a referenced record no longer exists",
                            message_id,
                            exc_info=True,
                        )
                        await asyncio.to_thread(
                            redis_client.xack,
                            stream,
                            NOTIFICATION_CONSUMER_GROUP,
                            message_id,
                        )
                    except Exception:
                        logger.exception(
                            "Could not persist queued notification %s; it will be retried",
                            message_id,
                        )
        except asyncio.CancelledError:
            raise
        except RedisError:
            group_ready = False
            logger.exception("Redis notification worker failed; retrying shortly")
            await asyncio.sleep(2)
