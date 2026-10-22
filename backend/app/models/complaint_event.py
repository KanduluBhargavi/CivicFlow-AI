from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ComplaintEvent(Base):
    __tablename__ = "complaint_events"

    event_id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.complaint_id"), nullable=False, index=True)
    event_type = Column(String(40), nullable=False)
    title = Column(String(160), nullable=False)
    detail = Column(Text, nullable=True)
    actor = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
