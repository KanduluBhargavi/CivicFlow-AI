from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app.utils.dependencies import get_current_user


from app.models.user import User
from sqlalchemy import desc
from datetime import datetime, timezone, timedelta
import statistics

from app.database import get_db
from app.models.complaint import Complaint
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_event import ComplaintEvent
from app.models.department import Department
from app.utils.workflow_status import complaint_display_status
from app.services.escalation_service import complaint_sla_state
from app.services.sla_service import sla_info

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])



@router.get("/stats")
def dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total, resolved = (
        db.query(
            func.count(Complaint.complaint_id),
            func.coalesce(func.sum(case((Complaint.status == "Resolved", 1), else_=0)), 0),
        )
        .filter(Complaint.citizen_id == current_user.user_id)
        .one()
    )
    total = int(total or 0)
    resolved = int(resolved or 0)
    return {
        "total_complaints": total,
        "pending": total - resolved,
        "resolved": resolved,
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
    ids = [complaint.complaint_id for complaint, _ in complaints]
    assigned_ids = {row[0] for row in db.query(ComplaintAssignment.complaint_id).filter(ComplaintAssignment.complaint_id.in_(ids)).all()} if ids else set()

    for complaint, department in complaints:
        data.append({
        "complaint_id": complaint.complaint_id,
        "title": complaint.title,
        "department": department.department_name,
        "status": complaint.status,
        "display_status": complaint_display_status(complaint.status, complaint.complaint_id in assigned_ids),
        "priority": complaint.priority
    })

    return data

@router.get("/activity-center")
def activity_center(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    latest_complaint = (
        db.query(Complaint)
        .filter(Complaint.citizen_id == current_user.user_id)
        .order_by(desc(Complaint.created_at))
        .first()
    )
    if not latest_complaint:
        return {"priority_alert": None, "latest_activity": None, "ai_routing": None}

    priority_rank = case(
        (Complaint.priority == "Critical", 4),
        (Complaint.priority == "High", 3),
        (Complaint.priority == "Medium", 2),
        (Complaint.priority == "Low", 1),
        else_=0,
    )
    highest = (
        db.query(Complaint)
        .filter(
            Complaint.citizen_id == current_user.user_id,
            Complaint.status != "Resolved",
        )
        .order_by(priority_rank.desc(), Complaint.created_at.desc())
        .first()
    )

    priority_alert = None if not highest else {
        "complaint_id": highest.complaint_id,
        "title": highest.title,
        "priority": highest.priority,
        "status": highest.status,
        "department": highest.predicted_department,
    }
    return {
        "priority_alert": priority_alert,
        "latest_activity": {
            "complaint_id": latest_complaint.complaint_id,
            "title": latest_complaint.title,
            "status": latest_complaint.status,
            "created_at": latest_complaint.created_at,
        },
        "ai_routing": {
            "complaint_id": latest_complaint.complaint_id,
            "title": latest_complaint.title,
            "department": latest_complaint.predicted_department,
            "priority": latest_complaint.priority,
        },
    }


@router.get("/notifications")
def citizen_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Latest citizen complaint events using one joined query."""
    visible_event_types = {
        "created", "officer_assignment", "smart_officer_assignment",
        "status", "resolution_proof", "manual_reroute", "reroute",
        "citizen_reopen",
        "translation_feedback", "translation_feedback_review",
    }
    rows = (
        db.query(ComplaintEvent, Complaint.title)
        .join(Complaint, Complaint.complaint_id == ComplaintEvent.complaint_id)
        .filter(
            Complaint.citizen_id == current_user.user_id,
            ComplaintEvent.event_type.in_(visible_event_types),
        )
        .order_by(ComplaintEvent.created_at.desc())
        .limit(40)
        .all()
    )

    def event_message(event):
        if event.event_type == "created":
            return "Complaint received by the department and awaiting individual officer assignment."
        if event.event_type == "resolution_proof":
            return "Resolution proof has been uploaded. Please review it and confirm whether the issue is resolved."
        if event.event_type == "citizen_reopen":
            return "Your complaint was reopened and returned to In Progress."
        return event.title

    notifications = [{
        "id": event.event_id,
        "complaint_id": event.complaint_id,
        "complaint_title": complaint_title,
        "type": event.event_type,
        "title": event_message(event),
        "detail": event.detail,
        "actor": event.actor,
        "created_at": event.created_at,
    } for event, complaint_title in rows]
    return {"count": len(notifications), "notifications": notifications}

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

@router.get("/public-stats")
def public_stats(db: Session = Depends(get_db)):

    total = db.query(Complaint).count()

    resolved = db.query(Complaint).filter(
        Complaint.status == "Resolved"
    ).count()

    pending = db.query(Complaint).filter(
        Complaint.status != "Resolved"
    ).count()

    departments = db.query(Department).count()

    return {
        "total_complaints": total,
        "resolved": resolved,
        "pending": pending,
        "departments": departments
    }


@router.get("/public-service-levels")
def public_service_levels(db: Session = Depends(get_db)):
    """Privacy-safe 90-day service-level summaries by district and department."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=90)
    rows = (
        db.query(Complaint, Department.department_name)
        .outerjoin(Department, Complaint.department_id == Department.department_id)
        .filter(Complaint.created_at >= cutoff)
        .all()
    )
    groups = {}
    for complaint, department_name in rows:
        district = (complaint.district or "").strip()
        state = (complaint.state or "").strip()
        department = (department_name or complaint.predicted_department or "Unassigned").strip()
        if not district or not state:
            continue
        key = (state, district, department)
        group = groups.setdefault(key, {
            "total": 0, "resolved": 0, "overdue": 0,
            "resolution_hours": [], "sla_met": 0, "sla_eligible": 0,
        })
        group["total"] += 1
        if complaint.status == "Resolved":
            group["resolved"] += 1
            start = complaint.assigned_at or complaint.created_at
            end = complaint.resolved_at
            if start and end:
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                hours = max(0, (end - start).total_seconds() / 3600)
                group["resolution_hours"].append(hours)
                target_hours = sla_info(complaint, db)["target_hours"]
                if target_hours is not None:
                    group["sla_eligible"] += 1
                    if hours <= target_hours:
                        group["sla_met"] += 1
        elif complaint_sla_state(complaint, db) == "Breached":
            group["overdue"] += 1

    published = []
    for (state, district, department), values in groups.items():
        # Avoid publishing small cells that could make individual cases inferable.
        if values["total"] < 5:
            continue
        published.append({
            "state": state,
            "district": district,
            "department": department,
            "complaints": values["total"],
            "resolved": values["resolved"],
            "resolution_rate": round(values["resolved"] * 100 / values["total"], 1),
            "overdue_open": values["overdue"],
            "median_resolution_hours": round(statistics.median(values["resolution_hours"]), 1) if values["resolution_hours"] else None,
            "sla_met_rate": round(values["sla_met"] * 100 / values["sla_eligible"], 1) if values["sla_eligible"] else None,
        })
    published.sort(key=lambda item: (-item["complaints"], item["state"], item["district"], item["department"]))
    return {
        "period_days": 90,
        "generated_at": now.isoformat(),
        "minimum_group_size": 5,
        "groups": published,
        "suppressed_groups": sum(1 for values in groups.values() if values["total"] < 5),
    }

@router.get("/public-recent-complaints")
def public_recent_complaints(db: Session = Depends(get_db)):

    complaints = (
        db.query(Complaint, Department)
        .join(
            Department,
            Complaint.department_id == Department.department_id
        )
        .order_by(desc(Complaint.created_at))
        .limit(5)
        .all()
    )

    data = []

    for complaint, department in complaints:

        data.append({
            "complaint_id":complaint.complaint_id,
            "title": complaint.title,
            "department":department.department_name,
            "priority": complaint.priority,
            "status": complaint.status,
            "district": complaint.district,
            "state": complaint.state

        })

    return data

@router.get("/map-data")
def map_data(db: Session = Depends(get_db)):
    """Return one privacy-limited marker per geolocated complaint."""
    rows = (
        db.query(Complaint, Department.department_name)
        .outerjoin(Department, Complaint.department_id == Department.department_id)
        .filter(
            Complaint.latitude.isnot(None), Complaint.longitude.isnot(None),
            Complaint.latitude != 0, Complaint.longitude != 0,
            Complaint.latitude.between(-90, 90), Complaint.longitude.between(-180, 180),
        )
        .all()
    )
    result = []
    for complaint, department_name in rows:
        result.append({
            "latitude": float(complaint.latitude),
            "longitude": float(complaint.longitude),
            "priority": complaint.priority or "Low",
            "status": complaint.status or "Submitted",
            "department": department_name or complaint.predicted_department or "Unassigned",
            "district": complaint.district,
            "state": complaint.state,
        })
    return result
