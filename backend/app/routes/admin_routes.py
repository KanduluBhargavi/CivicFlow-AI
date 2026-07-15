from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.user import User
from app.utils.auth import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/complaints")
def get_all_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role.lower() != "admin":
        return {"message": "Unauthorized"}

    complaints = db.query(Complaint).all()

    return complaints

@router.get("/analytics/total-complaints")
def total_complaints(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role.lower() != "admin":
        return {"message": "Unauthorized"}

    total = db.query(Complaint).count()

    return {
        "total_complaints": total
    }

@router.get("/analytics/total-users")
def total_users(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role.lower() != "admin":
        return {"message": "Unauthorized"}

    total = db.query(User).count()

    return {
        "total_users": total
    }

@router.get("/analytics/status")
def complaint_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role.lower() != "admin":
        return {"message": "Unauthorized"}

    result = (
        db.query(
            Complaint.status,
            func.count(Complaint.complaint_id)
        )
        .group_by(Complaint.status)
        .all()
    )

    return result


@router.get("/analytics/priority")
def complaint_priority(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role.lower() != "admin":
        return {"message": "Unauthorized"}

    result = (
        db.query(
            Complaint.priority,
            func.count(Complaint.complaint_id)
        )
        .group_by(Complaint.priority)
        .all()
    )

    return result

@router.get("/analytics/department")
def complaints_department(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    if current_user.role.lower() != "admin":
        return {"message": "Unauthorized"}

    result = (
        db.query(
            Complaint.predicted_department,
            func.count(Complaint.complaint_id)
        )
        .group_by(
            Complaint.predicted_department
        )
        .all()
    )

    return result