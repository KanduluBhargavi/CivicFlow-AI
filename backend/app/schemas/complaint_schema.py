from pydantic import BaseModel

class ComplaintCreate(BaseModel):
    title:str
    description:str