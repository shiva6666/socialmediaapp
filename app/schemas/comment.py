from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class CommentAuthor(BaseModel):
    id: int
    username: str
    full_name: str | None

    model_config = ConfigDict(from_attributes=True)


class CommentRead(BaseModel):
    id: int
    post_id: int
    body: str
    created_at: datetime
    author: CommentAuthor

    model_config = ConfigDict(from_attributes=True)


class LikeCount(BaseModel):
    post_id: int
    likes_count: int
