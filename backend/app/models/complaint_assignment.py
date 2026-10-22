from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from sqlalchemy.sql import func
from app.database import Base


class ComplaintAssignment(Base):
    __tablename__ = "complaint_assignments"

    assignment_id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.complaint_id"), unique=True, nullable=False, index=True)
    officer_id = Column(Integer, ForeignKey("users.user_id"), nullable=False, index=True)
    assigned_by = Column(String(120), nullable=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
