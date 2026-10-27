from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class NotificationActor(BaseModel):
    id: int
    username: str
    full_name: str | None

    model_config = ConfigDict(from_attributes=True)


class NotificationRead(BaseModel):
    id: int
    event_type: Literal["follow", "like", "comment"]
    post_id: int | None
    created_at: datetime
    read_at: datetime | None
    actor: NotificationActor

    model_config = ConfigDict(from_attributes=True)
