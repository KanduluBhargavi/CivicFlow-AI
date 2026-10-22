from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class TranslationFeedback(Base):
    __tablename__ = "translation_feedback"

    feedback_id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.complaint_id"), nullable=False, index=True)
    citizen_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    issue_type = Column(String(40), nullable=False, default="translation", server_default="translation")
    note = Column(Text, nullable=False)
    suggested_english = Column(Text, nullable=True)
    status = Column(String(24), nullable=False, default="Open", index=True)
    reviewed_by = Column(String(160), nullable=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
