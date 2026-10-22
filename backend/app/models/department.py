from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import relationship
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(100), nullable=False)
    description = Column(String(255))
    department_code = Column(String(30), unique=True, nullable=True)
    head_name = Column(String(120), nullable=True)
    state = Column(String(80), nullable=True)
    jurisdiction = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True)
    ai_supported = Column(Boolean, default=False)

    complaints = relationship("Complaint", back_populates="department")
    department_email = Column(String(100), unique=True, nullable=False, index=True)

    username = Column(String(100), unique=True, nullable=False, index=True)

    password = Column(String(255), nullable=False)




