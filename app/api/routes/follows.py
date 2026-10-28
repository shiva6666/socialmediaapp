from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.feed_cache import invalidate_feed_cache
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.follow import Follow
from app.models.user import User
from app.services.notifications import queue_notification

router = APIRouter()


@router.post("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow_user(
    username: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    target_user = db.scalar(select(User).where(User.username == username))
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if target_user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot follow yourself")

    existing_follow = db.get(Follow, (current_user.id, target_user.id))
    if existing_follow:
        return None

    db.add(Follow(follower_id=current_user.id, following_id=target_user.id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent request may have created the same follow relationship.
        return None

    invalidate_feed_cache([current_user.id])
    queue_notification(
        background_tasks,
        recipient_id=target_user.id,
        actor_id=current_user.id,
        event_type="follow",
    )
    return None


@router.delete("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def unfollow_user(
    username: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    target_user = db.scalar(select(User).where(User.username == username))
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    follow = db.get(Follow, (current_user.id, target_user.id))
    if follow:
        db.delete(follow)
        db.commit()
        invalidate_feed_cache([current_user.id])
    return None
