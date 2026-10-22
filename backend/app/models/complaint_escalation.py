from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base


class ComplaintEscalation(Base):
    __tablename__ = "complaint_escalations"

    escalation_id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.complaint_id"), nullable=False, index=True)
    level = Column(Integer, nullable=False, default=1, index=True)
    reason = Column(Text, nullable=False)
    source = Column(String(20), nullable=False, default="Automatic")
    status = Column(String(20), nullable=False, default="Open", index=True)
    escalated_by = Column(String(120), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
