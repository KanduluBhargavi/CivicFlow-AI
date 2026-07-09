from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.complaint import Complaint
from app.schemas.complaint_schema import ComplaintCreate

from app.services.ai_service import (detect_language, translate_text, predict_department, predict_priority, summarize_complaint)

router=APIRouter()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/complaints")
def create_complaint(complaint: ComplaintCreate, db:Session=Depends(get_db)):
    language=detect_language(complaint.description)
    translated_text=translate_text(complaint.description)
    predicted_department=predict_department(translated_text)
    priority=predict_priority(translated_text)
    summary=summarize_complaint(translated_text)

    new_complaint=Complaint(
        citizen_id=1,
        department_id=1,
        title=complaint.title,
        description=complaint.description,
        language=language,
        translated_text=translated_text,
        predicted_department=predicted_department,
        priority=priority,
        ai_summary=summary
    )

    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    return{
        "message":"Complaint Submitted Successfully",
        "complaint_id": new_complaint.complaint_id
    }

@router.get("/compliants")
def get_all_compliants(db: Session=Depends(get_db)):
    complaints=db.query(Complaint).all()
    return complaints