from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy import Float
from app.database import Base
from sqlalchemy.orm import relationship

class Complaint(Base):
    __tablename__="complaints"
    complaint_id=Column(Integer, primary_key=True, index=True)
    citizen_id =Column(Integer, ForeignKey("users.user_id"), index=True)
    department_id=Column(Integer, ForeignKey("departments.department_id"), index=True)

    title=Column(String(200),nullable=False)
    description=Column(Text, nullable=False)
    state = Column(String, nullable=False)

    district = Column(String, nullable=False, index=True)
    area = Column(String, nullable=False)

    address = Column(Text, nullable=False)

    landmark = Column(String, nullable=True)

    pincode = Column(String, nullable=False, index=True)

    latitude = Column(Float, nullable=True)

    longitude = Column(Float, nullable=True)
    media_path=Column(String, nullable=True)

    language=Column(String(30))
    translated_text=Column(Text)
    # English operational copies for department workflows.
    # Original citizen-entered values above remain unchanged.
    translated_title=Column(String(300), nullable=True)
    translated_area=Column(String(300), nullable=True)
    translated_address=Column(Text, nullable=True)
    translated_landmark=Column(String(300), nullable=True)
    predicted_department=Column(String(100))
    department_confidence=Column(Float, nullable=True)

    priority=Column(String(20))
    priority_confidence=Column(Float, nullable=True)
    priority_reason=Column(Text, nullable=True)
    # Dynamic priority engine (see services/priority_engine.py)
    base_priority=Column(String(20), nullable=True)      # ML text-based starting point
    priority_score=Column(Float, nullable=True)          # 0-100 live urgency score
    priority_factors=Column(Text, nullable=True)         # JSON: ML state + factor breakdown
    priority_updated_at=Column(DateTime(timezone=True), nullable=True)
    verified_emergency=Column(Boolean, default=False)    # verified emergency alert for this location
    ai_summary=Column(Text)

    # Sentiment Analysis (frustration detection)
    sentiment=Column(String(20))

    # Feature 6: Duplicate Detection
    is_duplicate = Column(Boolean, default=False)
    duplicate_of_id = Column(Integer, ForeignKey("complaints.complaint_id"), nullable=True)
    duplicate_match_id = Column(Integer, nullable=True)
    duplicate_confidence = Column(Float, default=0.0)
    duplicate_similarity = Column(Float, default=0.0)
    duplicate_classification = Column(String(20), default="none")
    duplicate_reason = Column(Text, nullable=True)
    location_source = Column(String(30), default="district_centroid")
    # Persisted incident cluster. Every complaint in one incident shares this ID.
    incident_cluster_id = Column(Integer, nullable=True, index=True)

    status=Column(String(30), default="Submitted", index=True)
    assigned_at = Column(DateTime, nullable=True)
    # Snapshot of the text/priority/history-based expected resolution target.
    sla_target_hours = Column(Float, nullable=True)
    sla_target_lower_hours = Column(Float, nullable=True)
    sla_target_upper_hours = Column(Float, nullable=True)
    sla_target_sample_size = Column(Integer, nullable=True)
    sla_target_basis = Column(String(80), nullable=True)
    sla_target_priority = Column(String(20), nullable=True)
    officer_assignment_due_at = Column(DateTime(timezone=True), nullable=True)

    in_progress_at = Column(DateTime, nullable=True)

    resolved_at = Column(DateTime, nullable=True)

    resolution_proof_path = Column(String, nullable=True)
    resolution_note = Column(Text, nullable=True)
    citizen_resolution_status = Column(String(30), nullable=True)
    citizen_resolution_note = Column(Text, nullable=True)
    citizen_confirmed_at = Column(DateTime(timezone=True), nullable=True)

    created_at=Column(DateTime(timezone=True), server_default=func.now(), index=True)
    department = relationship("Department", back_populates="complaints")
