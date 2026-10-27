from typing import Literal

from sqlalchemy.orm import Session

from app.models.notification import Notification


def add_notification(
    db: Session,
    recipient_id: int,
    actor_id: int,
    event_type: Literal["follow", "like", "comment"],
    post_id: int | None = None,
) -> None:
    if recipient_id == actor_id:
        return

    db.add(
        Notification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            event_type=event_type,
            post_id=post_id,
        )
    )
