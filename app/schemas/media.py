from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaRead(BaseModel):
    id: int
    url: str
    content_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
