from sqlalchemy import Column, Integer, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base


class ComplaintSupport(Base):
    __tablename__ = "complaint_supports"
    __table_args__ = (
        UniqueConstraint("incident_cluster_id", "citizen_id", name="uq_incident_citizen_support"),
    )

    support_id = Column(Integer, primary_key=True, index=True)
    incident_cluster_id = Column(Integer, nullable=False, index=True)
    citizen_id = Column(Integer, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
