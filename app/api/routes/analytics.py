from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.analytics_event import AnalyticsEvent
from app.models.user import User
from app.schemas.analytics import AnalyticsEventCreate, AnalyticsEventRead
from app.services.analytics import record_event

router = APIRouter()


@router.post(
    "/events",
    response_model=AnalyticsEventRead,
    status_code=status.HTTP_201_CREATED,
)
def track_event(
    payload: AnalyticsEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsEvent:
    return record_event(db, user_id=current_user.id, payload=payload)
