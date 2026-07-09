from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Complaint(Base):
    __tablename__="complaints"
    complaint_id=Column(Integer, primary_key=True, index=True)
    citizen_id =Column(Integer, ForeignKey("users.user_id"))
    department_id=Column(Integer, ForeignKey("departments.department_id"))

    title=Column(String(200),nullable=False)
    description=Column(Text, nullable=False)

    language=Column(String(30))
    translated_text=Column(Text)
    predicted_department=Column(String(100))

    priority=Column(String(20))
    ai_summary=Column(Text)
    status=Column(String(30), default="Submitted")

    created_at=Column(DateTime(timezone=True), server_default=func.now())
