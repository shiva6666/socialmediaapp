from sqlalchemy.orm import Session

from app.models.analytics_event import AnalyticsEvent
from app.schemas.analytics import AnalyticsEventCreate


def record_event(
    db: Session, user_id: int, payload: AnalyticsEventCreate
) -> AnalyticsEvent:
    event = AnalyticsEvent(
        user_id=user_id,
        event_name=payload.event_name,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event
