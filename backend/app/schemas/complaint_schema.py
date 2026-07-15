from pydantic import BaseModel

class ComplaintCreate(BaseModel):
    title:str
    description:str
    state: str
    district: str
    area: str
    address: str
    landmark: str | None = None
    pincode: str
    latitude: float | None = None
    longitude: float | None = None