from fastapi import APIRouter, Depends,Form
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.contact import ContactMessage
router=APIRouter(prefix="/contact", tags=["Contact"])

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/")
def send_message(
    name:str=Form(...),
    email:str=Form(...),
    subject:str=Form(...),
    message:str=Form(...),
    db:Session=Depends(get_db)
):
    new_message=ContactMessage(
        name=name,
        email=email,
        subject=subject,
        message=message
    )

    db.add(new_message)
    db.commit()
    db.refresh(new_message)

    return{
        "message":"Message sent successfully!"
    }