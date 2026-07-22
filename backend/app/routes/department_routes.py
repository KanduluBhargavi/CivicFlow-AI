from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.schemas.department_schema import ComplaintStatusUpdate
from fastapi import HTTPException
from app.database import get_db
from app.models.complaint import Complaint
from app.models.department import Department
from app.utils.dependencies import get_current_department
from datetime import datetime, timezone

router = APIRouter(prefix="/department", tags=["Department"])

@router.get("/dashboard")
def dashboard(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    total = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id
    ).count()


    in_progress = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id,
        Complaint.status == "In Progress"
    ).count()

    resolved = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id,
        Complaint.status == "Resolved"
    ).count()

    pending=total-resolved

    high_priority = db.query(Complaint).filter(
    Complaint.department_id == current_department.department_id,
    Complaint.priority == "High"
    ).count() 

    return {
        "total": total,
        "pending":pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "high_priority": high_priority
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



@router.get("/complaint/{complaint_id}")
def get_department_complaint(
    complaint_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):

    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.complaint_id == complaint_id,
            Complaint.department_id == current_department.department_id
        )
        .first()
    )

    if complaint is None:
        raise HTTPException(
            status_code=404,
            detail="Complaint not found"
        )

    return {

        "complaint_id": complaint.complaint_id,

        "title": complaint.title,

        "description": complaint.description,

        "priority": complaint.priority,

        "status": complaint.status,

        "department": current_department.department_name,

        "state": complaint.state,

        "district": complaint.district,

        "area": complaint.area,

        "address": complaint.address,

        "landmark": complaint.landmark,

        "pincode": complaint.pincode,

        "ai_summary": complaint.ai_summary,

        "media_url": complaint.media_path,

        "created_at": complaint.created_at,

        "assigned_at": complaint.assigned_at,

        "in_progress_at": complaint.in_progress_at,

        "resolved_at": complaint.resolved_at

    }

@router.put("/update-status/{complaint_id}")
def update_status(

    complaint_id: int,

    status_data: ComplaintStatusUpdate,

    current_department: Department = Depends(get_current_department),

    db: Session = Depends(get_db)

):

    complaint = (

        db.query(Complaint)

        .filter(

            Complaint.complaint_id == complaint_id,

            Complaint.department_id == current_department.department_id

        )

        .first()

    )

    if complaint is None:

        raise HTTPException(

            status_code=404,

            detail="Complaint not found"

        )

    allowed_status = [

        "Assigned",

        "In Progress",

        "Resolved"

    ]

    if status_data.status not in allowed_status:

        raise HTTPException(

            status_code=400,

            detail="Invalid Status"

        )

    complaint.status = status_data.status

    if status_data.status == "In Progress":

        complaint.in_progress_at = datetime.now(timezone.utc)

    elif status_data.status == "Resolved":

        complaint.resolved_at = datetime.now(timezone.utc)

    db.commit()

    db.refresh(complaint)

    return {

        "message": "Status Updated Successfully"

    }




