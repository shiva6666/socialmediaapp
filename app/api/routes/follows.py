from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.follow import Follow
from app.models.user import User

router = APIRouter()


@router.post("/{username}/follow", status_code=status.HTTP_204_NO_CONTENT)
def follow_user(
    username: str,
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
    return None
