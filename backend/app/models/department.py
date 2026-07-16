from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.database import Base

class Department(Base):
    __tablename__ = "departments"

    department_id = Column(Integer, primary_key=True, index=True)
    department_name = Column(String(100), nullable=False)
    description = Column(String(255))

    complaints = relationship("Complaint", back_populates="department")
    department_email = Column(String(100), unique=True, nullable=False)

    username = Column(String(100), unique=True, nullable=False)

    password = Column(String(255), nullable=False)




