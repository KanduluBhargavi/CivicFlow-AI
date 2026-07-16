from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.database import get_db
from app.models.complaint import Complaint
from app.models.department import Department
from app.utils.dependencies import get_current_department

router = APIRouter(prefix="/department", tags=["Department"])

@router.get("/dashboard")
def dashboard(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):

    assigned = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id
    ).count()

    pending = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id,
        Complaint.status == "Submitted"
    ).count()

    in_progress = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id,
        Complaint.status == "In Progress"
    ).count()

    resolved = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id,
        Complaint.status == "Resolved"
    ).count()

    return {
        "assigned": assigned,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved
    }

@router.get("/complaints")
def department_complaints(
    
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    
    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.department_id == current_department.department_id
        )
        .order_by(desc(Complaint.created_at))
        .all()
    )

    data = []

    for c in complaints:

        data.append({

            "complaint_id": c.complaint_id,

            "title": c.title,

            "priority": c.priority,

            "status": c.status,

            "created_at": c.created_at

        })

    return data

