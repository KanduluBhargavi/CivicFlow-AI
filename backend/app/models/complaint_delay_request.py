from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class ComplaintDelayRequest(Base):
    __tablename__ = "complaint_delay_requests"

    request_id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.complaint_id"), nullable=False, index=True)
    officer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    blocker_category = Column(String(40), nullable=False)
    requested_until = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(24), nullable=False, default="Pending Head Review", index=True)
    manager_note = Column(Text, nullable=True)
    reviewed_by = Column(String(120), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    followup_sent = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
