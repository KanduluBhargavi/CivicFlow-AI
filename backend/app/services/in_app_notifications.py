from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.in_app_notification import InAppNotification


def create_notification(
    db: Session, *, notification_type: str, title: str, message: str,
    complaint_id: int | None = None, recipient_user_id: int | None = None,
    recipient_department_id: int | None = None, dedupe_key: str | None = None,
):
    """Create a persistent inbox item. Stable dedupe keys make polling idempotent."""
    if recipient_user_id is None and recipient_department_id is None:
        return None
    if dedupe_key:
        existing = db.query(InAppNotification).filter(
            InAppNotification.dedupe_key == dedupe_key
        ).first()
        if existing:
            return existing
    item = InAppNotification(
        recipient_user_id=recipient_user_id,
        recipient_department_id=recipient_department_id,
        complaint_id=complaint_id,
        notification_type=notification_type[:40],
        title=title[:180],
        message=message,
        dedupe_key=dedupe_key,
        created_at=datetime.now(timezone.utc),
    )
    db.add(item)
    db.flush()
    return item
