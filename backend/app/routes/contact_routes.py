from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas.feedback_schema import FeedbackCreate
from app.database import SessionLocal
from app.models.contact import Feedback
from app.models.user import User
from app.utils.auth import get_current_user


router = APIRouter(
    prefix="/feedback",
    tags=["Feedback"]
)


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


# =====================================
# SUBMIT FEEDBACK
# =====================================

@router.post("/")
def submit_feedback(
    feedback: FeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    new_feedback = Feedback(
        user_id=current_user.user_id,
        rating=feedback.rating,
        message=feedback.message.strip()
    )

    db.add(new_feedback)
    db.commit()
    db.refresh(new_feedback)

    return {
        "message": "Thank you for your feedback!",
        "feedback_id": new_feedback.feedback_id
    }


# ==========================================
# GET ALL FEEDBACK - ADMIN
# ==========================================

@router.get("/")
def get_all_feedback(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # Only admin can see everyone's feedback
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=403,
            detail="Only admin can view all feedback"
        )

    feedback_list = (
        db.query(Feedback)
        .order_by(Feedback.created_at.desc())
        .all()
    )

    result = []

    for feedback in feedback_list:

        user = db.query(User).filter(
            User.user_id == feedback.user_id
        ).first()

        result.append({
            "feedback_id": feedback.feedback_id,
            "user_name": user.full_name if user else "Unknown User",
            "email": user.email if user else "",
            "rating": feedback.rating,
            "message": feedback.message,
            "created_at": feedback.created_at
        })

    return result

@router.get("/recent")
def get_recent_feedback(db: Session = Depends(get_db)):
    recent_feedback = (db.query(Feedback, User).join(User, Feedback.user_id == User.user_id).order_by(Feedback.created_at.desc()).limit(6).all())


    result = []

    for feedback, user in recent_feedback:
        result.append({
        "feedback_id": feedback.feedback_id,
        "user_name": user.full_name,
        "rating": feedback.rating,
        "message": feedback.message,
        "created_at": feedback.created_at
    })

    return result

