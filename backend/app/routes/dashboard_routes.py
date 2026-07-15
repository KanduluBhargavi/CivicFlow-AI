from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.utils.dependencies import get_current_user


from app.models.user import User
from sqlalchemy import desc

from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.department import Department

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/stats")
def dashboard_stats(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    total = db.query(Complaint).filter(
    Complaint.citizen_id == current_user.user_id).count()

    resolved = db.query(Complaint).filter(
    Complaint.citizen_id == current_user.user_id,
    Complaint.status == "Resolved").count()

    pending = db.query(Complaint).filter(
    Complaint.citizen_id == current_user.user_id,
    Complaint.status != "Resolved").count()

    departments = db.query(Department).count()

    return {
    "total_complaints": total,
    "pending": pending,
    "resolved": resolved,
    "rejected": 0
}
@router.get("/recent-complaints")
def recent_complaints(current_user: User = Depends(get_current_user),db: Session = Depends(get_db)):
    complaints = (
    db.query(Complaint, Department)
    .join(
        Department,
        Complaint.department_id == Department.department_id
    )
    .filter(
        Complaint.citizen_id == current_user.user_id
    )
    .order_by(desc(Complaint.created_at))
    .limit(5)
    .all()
)

    data = []

    for complaint, department in complaints:

        data.append({
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "department": department.department_name,
        "status": complaint.status,
        "priority": complaint.priority
    })

    return data

@router.get("/top-states")
def top_states(db: Session = Depends(get_db)):

    states = (
        db.query(
            Complaint.state,
            func.count(Complaint.complaint_id).label("count")
        )
        .group_by(Complaint.state)
        .order_by(func.count(Complaint.complaint_id).desc())
        .limit(5)
        .all()
    )

    return [
        {
            "state": s.state,
            "count": s.count
        }
        for s in states
    ]


@router.get("/department-performance")
def department_performance(db: Session = Depends(get_db)):

    departments = (
        db.query(
            Department.department_name,
            func.count(Complaint.complaint_id).label("total")
        )
        .outerjoin(
            Complaint,
            Department.department_id == Complaint.department_id
        )
        .group_by(
            Department.department_name
        )
        .order_by(
            func.count(Complaint.complaint_id).desc()
        )
        .all()
    )

    return [
        {
            "department": d.department_name,
            "complaints": d.total
        }
        for d in departments
    ]

