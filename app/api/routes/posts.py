from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.follow import Follow
from app.models.post import Post
from app.models.user import User
from app.schemas.post import PostCreate, PostRead

router = APIRouter()


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
    return post


@router.get("/feed", response_model=list[PostRead])
def read_feed(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Post]:
    followed_user_ids = select(Follow.following_id).where(Follow.follower_id == current_user.id)
    query = (
        select(Post)
        .options(joinedload(Post.author))
        .where(Post.author_id.in_(followed_user_ids) | (Post.author_id == current_user.id))
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query).all())


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
        .options(joinedload(Post.author))
        .where(Post.author_id == author.id)
        .order_by(Post.created_at.desc(), Post.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query).all())
