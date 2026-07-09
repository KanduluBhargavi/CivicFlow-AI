from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.utils.auth import get_current_user
from app.models.user import User

from fastapi import UploadFile, File, Form
import os
import shutil
import uuid
from app.database import SessionLocal
from app.models.complaint import Complaint


from app.services.ai_service import (detect_language, translate_text, predict_department, predict_priority, summarize_complaint, get_department_id)

UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

router=APIRouter()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/complaints")
def create_complaint(
    title: str = Form(...),
    description: str = Form(...),
    file: UploadFile = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    language=detect_language(description)
    translated_text=translate_text(description)
    predicted_department=predict_department(translated_text)
    department_id = get_department_id(predicted_department)
    priority=predict_priority(translated_text)
    summary=summarize_complaint(translated_text)

    media_path = None

    if file:
         extension = os.path.splitext(file.filename)[1]

         unique_filename = f"{uuid.uuid4()}{extension}"

         media_path = os.path.join(
              UPLOAD_FOLDER,
              unique_filename
         )

         with open(media_path, "wb") as buffer:
              shutil.copyfileobj(file.file, buffer)

    new_complaint=Complaint(
        citizen_id=current_user.user_id,
        department_id=department_id,
        title=title,
        description=description,
        language=language,
        translated_text=translated_text,
        predicted_department=predicted_department,
        priority=priority,
        ai_summary=summary,
        media_path=media_path
    )

    db.add(new_complaint)
    db.commit()
    db.refresh(new_complaint)

    return{
        "message":"Complaint Submitted Successfully",
        "complaint_id": new_complaint.complaint_id
    }

@router.get("/my-complaints")
def my_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    complaints = (
        db.query(Complaint)
        .filter(Complaint.citizen_id == current_user.user_id)
        .all()
    )

    return complaints

@router.get("/department-complaints")
def department_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.department_id == current_user.department_id
        )
        .all()
    )

    return complaints
@router.put("/update-status/{complaint_id}")
def update_status(
    complaint_id: int,
    status: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id
    ).first()

    if not complaint:
        return {"message": "Complaint not found"}

    # Officer can update only complaints of their own department
    if complaint.department_id != current_user.department_id:
        return {"message": "Unauthorized"}

    complaint.status = status

    db.commit()
    db.refresh(complaint)

    return {
        "message": "Status Updated Successfully",
        "status": complaint.status
    }

@router.get("/compliants")
def get_all_compliants(db: Session=Depends(get_db)):
    complaints=db.query(Complaint).all()
    return complaints

