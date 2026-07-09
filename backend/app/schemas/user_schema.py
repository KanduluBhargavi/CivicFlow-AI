from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    full_name:str
    email:EmailStr
    phone:str
    password:str
    role:str
    department_id:int | None=None
    state:str
    district:str
    address:str
