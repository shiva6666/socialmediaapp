from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.feed_cache import invalidate_author_feeds
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.user import ProfileUpdate, UserRead

router = APIRouter()


@router.patch("/me", response_model=UserRead)
def update_my_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    if payload.username is not None:
        existing_user = db.scalar(
            select(User).where(
                User.username == payload.username,
                User.id != current_user.id,
            )
        )
        if existing_user is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="That username is already taken",
            )
        current_user.username = payload.username

    if "full_name" in payload.model_fields_set:
        current_user.full_name = payload.full_name

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That username is already taken",
        ) from None

    db.refresh(current_user)
    invalidate_author_feeds(db, current_user.id)
    return current_user
