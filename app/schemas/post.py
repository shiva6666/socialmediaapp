from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class PostAuthor(BaseModel):
    id: int
    username: str
    full_name: str | None

    model_config = ConfigDict(from_attributes=True)


class PostRead(BaseModel):
    id: int
    body: str
    created_at: datetime
    author: PostAuthor

    model_config = ConfigDict(from_attributes=True)
