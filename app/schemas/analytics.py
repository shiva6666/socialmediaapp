from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsEventCreate(BaseModel):
    event_name: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    entity_type: Literal["post", "user", "comment"] | None = None
    entity_id: int | None = Field(default=None, gt=0)


class AnalyticsEventRead(BaseModel):
    id: int
    event_name: str
    entity_type: str | None
    entity_id: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
