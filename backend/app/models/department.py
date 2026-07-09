from sqlalchemy import Column, Integer, String
from app.database import Base

class Department(Base):
    __tablename__="departments"

    department_id=Column(Integer, primary_key=True, index=True)
    department_name=Column(String(100), nullable=False)
    description=Column(String(255))