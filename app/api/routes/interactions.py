from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.comment import Comment
from app.models.like import Like
from app.models.post import Post
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead, LikeCount
from app.services.notifications import queue_notification

router = APIRouter()


def get_post_or_404(post_id: int, db: Session) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


@router.post("/posts/{post_id}/likes", status_code=status.HTTP_204_NO_CONTENT)
def like_post(
    post_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    post = get_post_or_404(post_id, db)
    existing_like = db.get(Like, (current_user.id, post_id))
    if existing_like is None:
        db.add(Like(user_id=current_user.id, post_id=post_id))
        db.commit()
        queue_notification(
            background_tasks,
            recipient_id=post.author_id,
            actor_id=current_user.id,
            event_type="like",
            post_id=post.id,
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/posts/{post_id}/likes", status_code=status.HTTP_204_NO_CONTENT)
def unlike_post(
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    get_post_or_404(post_id, db)
    like = db.get(Like, (current_user.id, post_id))
    if like is not None:
        db.delete(like)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/posts/{post_id}/likes/count", response_model=LikeCount)
def count_post_likes(post_id: int, db: Session = Depends(get_db)) -> LikeCount:
    get_post_or_404(post_id, db)
    count = db.scalar(select(func.count()).select_from(Like).where(Like.post_id == post_id))
    return LikeCount(post_id=post_id, likes_count=count or 0)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: int,
    payload: CommentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Comment:
    post = get_post_or_404(post_id, db)
    comment = Comment(post_id=post_id, user_id=current_user.id, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    queue_notification(
        background_tasks,
        recipient_id=post.author_id,
        actor_id=current_user.id,
        event_type="comment",
        post_id=post.id,
    )
    return comment


@router.get("/posts/{post_id}/comments", response_model=list[CommentRead])
def read_comments(
    post_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Comment]:
    get_post_or_404(post_id, db)
    query = (
        select(Comment)
        .options(joinedload(Comment.author))
        .where(Comment.post_id == post_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(query).all())


@router.delete(
    "/posts/{post_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_comment(
    post_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    comment = db.get(Comment, comment_id)
    if comment is None or comment.post_id != post_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only delete your own comments",
        )
    db.delete(comment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
