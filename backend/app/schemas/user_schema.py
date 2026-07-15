from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    full_name:str
    email:EmailStr
    phone:str
    password:str
    
    department_id:int | None=None
    state:str
    district:str
    address:str
    area: str
    landmark: str
    pincode: str
   

    latitude: Optional[float] = None
    longitude: Optional[float] = None
