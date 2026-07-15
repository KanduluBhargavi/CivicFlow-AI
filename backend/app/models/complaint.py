from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy import Float
from app.database import Base
from sqlalchemy.orm import relationship

class Complaint(Base):
    __tablename__="complaints"
    complaint_id=Column(Integer, primary_key=True, index=True)
    citizen_id =Column(Integer, ForeignKey("users.user_id"))
    department_id=Column(Integer, ForeignKey("departments.department_id"))

    title=Column(String(200),nullable=False)
    description=Column(Text, nullable=False)
    state = Column(String, nullable=False)

    district = Column(String, nullable=False)
    area = Column(String, nullable=False)

    address = Column(Text, nullable=False)

    landmark = Column(String, nullable=True)

    pincode = Column(String, nullable=False)

    latitude = Column(Float, nullable=True)

    longitude = Column(Float, nullable=True)
    media_path=Column(String, nullable=True)

    language=Column(String(30))
    translated_text=Column(Text)
    predicted_department=Column(String(100))

    priority=Column(String(20))
    ai_summary=Column(Text)
    status=Column(String(30), default="Submitted")
    assigned_at = Column(DateTime, nullable=True)

    in_progress_at = Column(DateTime, nullable=True)

    resolved_at = Column(DateTime, nullable=True)

    created_at=Column(DateTime(timezone=True), server_default=func.now())
    department = relationship("Department", back_populates="complaints")