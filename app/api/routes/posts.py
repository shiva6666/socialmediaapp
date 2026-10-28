import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.core.feed_cache import (
    cache_feed,
    feed_cache_key,
    get_cached_feed,
    invalidate_author_feeds,
    invalidate_feed_cache,
)
from app.dependencies.auth import get_current_user
from app.models.follow import Follow
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostRead, PostUpdate

router = APIRouter()
logger = logging.getLogger(__name__)
feed_adapter = TypeAdapter(list[PostRead])


@router.post("", response_model=PostRead, status_code=status.HTTP_201_CREATED)
def create_post(
    payload: PostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Post:
    post = Post(body=payload.body, author_id=current_user.id)
    db.add(post)
    db.commit()
    db.refresh(post)
    invalidate_author_feeds(db, current_user.id)
    return post


@router.get("/feed", response_model=list[PostRead])
def read_feed(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PostRead]:
    cache_key = feed_cache_key(current_user.id, limit, offset)
    cached_feed = get_cached_feed(cache_key)
    if cached_feed is not None:
        try:
            return feed_adapter.validate_json(cached_feed)
        except (ValueError, ValidationError):
            logger.warning("Discarding invalid cached feed for user %s", current_user.id)
            invalidate_feed_cache([current_user.id])

    followed_user_ids = select(Follow.following_id).where(Follow.follower_id == current_user.id)
    query = (
        select(Post)
        .options(joinedload(Post.author), selectinload(Post.media))
        .where(Post.author_id.in_(followed_user_ids) | (Post.author_id == current_user.id))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    )
    feed = [
        PostRead.model_validate(post)
        for post in db.scalars(query).unique().all()
    ]
    cache_feed(
        cache_key,
        feed_adapter.dump_json(feed).decode("utf-8"),
        settings.feed_cache_ttl_seconds,
    )
    return feed


@router.get("/users/{username}", response_model=list[PostRead])
def read_user_posts(
    username: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Post]:
    author = db.scalar(select(User).where(User.username == username))
    if author is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    query = (
        select(Post)
        .options(joinedload(Post.author), selectinload(Post.media))
        .where(Post.author_id == author.id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query).all())


@router.patch("/{post_id}", response_model=PostRead)
def update_post(
    post_id: int,
    payload: PostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own posts",
        )

    post.body = payload.body
    db.commit()
    db.refresh(post)
    invalidate_author_feeds(db, current_user.id)
    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    if post.author_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own posts",
        )

    author_id = post.author_id
    uploaded_files = [Path(settings.media_dir) / item.file_name for item in post.media]
    db.delete(post)
    db.commit()
    invalidate_author_feeds(db, author_id)
    for uploaded_file in uploaded_files:
        uploaded_file.unlink(missing_ok=True)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
