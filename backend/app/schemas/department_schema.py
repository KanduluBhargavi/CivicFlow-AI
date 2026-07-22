from pydantic import BaseModel


class ComplaintStatusUpdate(BaseModel):

    status: str