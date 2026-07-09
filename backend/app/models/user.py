from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class User(Base):
    __tablename__="users"

    user_id=Column(Integer, primary_key=True, index=True)
    full_name=Column(String(100), nullable=False)
    email=Column(String(100), unique=True, nullable=False)
    phone=Column(String(15), unique=True)
    password=Column(String(255), nullable=False)
    role=Column(String(20),nullable=False)
    department_id=Column(Integer, ForeignKey("departments.department_id"), nullable=True)
    state=Column(String(50))
    district=Column(String(50))
    address=Column(String(255))
    