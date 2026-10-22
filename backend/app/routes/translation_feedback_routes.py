from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import SECRET_KEY, ALGORITHM
from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.translation_feedback import TranslationFeedback
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/translation-feedback", tags=["Translation Feedback"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if (payload.get("role") or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return payload


class TranslationFeedbackCreate(BaseModel):
    issue_type: str = Field(default="translation", max_length=40)
    source_text: Optional[str] = Field(default=None, max_length=5000)
    translated_text: Optional[str] = Field(default=None, max_length=5000)
    suggested_correction: Optional[str] = Field(default=None, max_length=5000)
    citizen_note: Optional[str] = Field(default=None, max_length=2000)


class TranslationFeedbackReview(BaseModel):
    status: str
    reviewer_note: Optional[str] = Field(default=None, max_length=2000)


@router.post("/complaints/{complaint_id}")
def submit_translation_feedback(
    complaint_id: int,
    payload: TranslationFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.citizen_id == current_user.user_id,
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    issue_type = payload.issue_type.strip().lower()
    allowed_types = {"translation", "english_summary", "title_or_location", "other"}
    if issue_type not in allowed_types:
        raise HTTPException(status_code=422, detail="Choose a valid translation issue type")
    if not (payload.suggested_correction or payload.citizen_note):
        raise HTTPException(status_code=400, detail="Add a suggested correction or describe the issue")

    item = TranslationFeedback(
        complaint_id=complaint.complaint_id,
        citizen_id=current_user.user_id,
        issue_type=issue_type,
        source_text=(payload.source_text or complaint.description or "")[:5000],
        translated_text=(payload.translated_text or complaint.translated_text or "")[:5000],
        suggested_correction=(payload.suggested_correction or "").strip() or None,
        citizen_note=(payload.citizen_note or "").strip() or None,
        status="Pending",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"message": "Translation issue submitted for review.", "feedback_id": item.feedback_id, "status": item.status}


@router.get("/admin")
def list_translation_feedback(
    status: Optional[str] = None,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(TranslationFeedback, Complaint, User).join(
        Complaint, Complaint.complaint_id == TranslationFeedback.complaint_id
    ).join(User, User.user_id == TranslationFeedback.citizen_id)
    if status:
        query = query.filter(TranslationFeedback.status == status)
    rows = query.order_by(TranslationFeedback.created_at.desc()).limit(300).all()
    return [{
        "feedback_id": item.feedback_id,
        "complaint_id": item.complaint_id,
        "complaint_title": complaint.title,
        "citizen_name": user.full_name,
        "citizen_email": user.email,
        "issue_type": item.issue_type,
        "source_text": item.source_text,
        "translated_text": item.translated_text,
        "suggested_correction": item.suggested_correction,
        "citizen_note": item.citizen_note,
        "status": item.status,
        "reviewer_note": item.reviewer_note,
        "reviewed_by": item.reviewed_by,
        "created_at": item.created_at,
        "reviewed_at": item.reviewed_at,
    } for item, complaint, user in rows]


@router.patch("/admin/{feedback_id}")
def review_translation_feedback(
    feedback_id: int,
    payload: TranslationFeedbackReview,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    allowed = {"Pending", "Reviewed", "Accepted", "Rejected"}
    if payload.status not in allowed:
        raise HTTPException(status_code=422, detail="Status must be Pending, Reviewed, Accepted or Rejected")
    item = db.query(TranslationFeedback).filter(TranslationFeedback.feedback_id == feedback_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Translation feedback not found")
    item.status = payload.status
    item.reviewer_note = (payload.reviewer_note or "").strip() or None
    item.reviewed_by = admin.get("sub")
    item.reviewed_at = datetime.now(timezone.utc) if payload.status != "Pending" else None
    db.commit()
    return {"message": "Translation feedback review saved.", "feedback_id": item.feedback_id, "status": item.status}
