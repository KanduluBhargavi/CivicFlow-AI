from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.sql import func
from app.database import Base


class InAppNotification(Base):
    """Persistent, recipient-scoped notification inbox for CivicFlow officers/managers."""
    __tablename__ = "in_app_notifications"

    notification_id = Column(Integer, primary_key=True, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=True, index=True)
    recipient_department_id = Column(Integer, ForeignKey("departments.department_id", ondelete="CASCADE"), nullable=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.complaint_id", ondelete="SET NULL"), nullable=True, index=True)
    notification_type = Column(String(40), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)
    dedupe_key = Column(String(240), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_in_app_notifications_user_read", "recipient_user_id", "read_at"),
        Index("ix_in_app_notifications_department_read", "recipient_department_id", "read_at"),
    )
