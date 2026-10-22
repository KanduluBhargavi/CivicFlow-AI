from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class ComplaintDeletion(Base):
    """Minimal audit trail for administrator complaint removals."""
    __tablename__ = "complaint_deletions"

    deletion_id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, nullable=False, index=True)
    deleted_by = Column(String(160), nullable=False)
    reason = Column(Text, nullable=False)
    deleted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
