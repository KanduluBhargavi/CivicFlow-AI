from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from jose import JWTError, jwt
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from typing import Optional
import io
import csv
import os
import statistics

from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.user import User
from app.models.department import Department
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_escalation import ComplaintEscalation
from app.models.complaint_event import ComplaintEvent
from app.models.complaint_deletion import ComplaintDeletion
from app.models.complaint_support import ComplaintSupport
from app.models.in_app_notification import InAppNotification
from app.models.contact import Feedback
from app.models.translation_feedback import TranslationFeedback
from app.services.escalation_service import sync_automatic_escalations
from app.services.priority_engine import refresh_priorities
from app.services.officer_metrics import officer_metrics_for_ids
from app.services.sla_service import sla_info
from app.utils.workflow_status import complaint_display_status
from app.utils.complaint_titles import display_operational_title
from app.config import SECRET_KEY, ALGORITHM
from app.utils.security import hash_password
from app.utils.location_normalization import normalize_state

router = APIRouter(prefix="/admin", tags=["Admin"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

AI_SUPPORTED_DEPARTMENTS = {
    "education", "electricity", "healthcare", "municipal corporation",
    "police", "roads & transport", "sanitation", "water supply"
}

class DepartmentCreate(BaseModel):
    department_name: str
    department_code: Optional[str] = None
    description: Optional[str] = None
    head_name: str
    department_email: str
    username: str
    password: str
    state: Optional[str] = None
    jurisdiction: Optional[str] = None


class ComplaintDeleteRequest(BaseModel):
    reason: str = Field(min_length=8, max_length=500)


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

def _sla_state(c, db=None):
    return sla_info(c, db)["state"]

@router.get("/overview")
def overview(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    total_complaints, resolved, in_progress, high_critical = (
        db.query(
            func.count(Complaint.complaint_id),
            func.coalesce(func.sum(case((Complaint.status == "Resolved", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Complaint.status == "In Progress", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Complaint.priority.in_(["High", "Critical"]), 1), else_=0)), 0),
        ).one()
    )
    total_users = db.query(func.count(User.user_id)).filter(func.lower(User.role) == "citizen").scalar() or 0
    total_officers = db.query(func.count(User.user_id)).filter(func.lower(User.role) == "officer").scalar() or 0
    total_departments = db.query(func.count(Department.department_id)).scalar() or 0

    unresolved = db.query(Complaint).filter(Complaint.status != "Resolved").all()
    assigned_ids = {r[0] for r in db.query(ComplaintAssignment.complaint_id).all()}

    total_complaints = int(total_complaints or 0)
    resolved = int(resolved or 0)
    in_progress = int(in_progress or 0)
    pending = total_complaints - resolved - in_progress
    return {
        "total_complaints": total_complaints,
        "total_users": int(total_users),
        "total_departments": int(total_departments),
        "total_officers": int(total_officers),
        "resolved": resolved,
        "in_progress": in_progress,
        "pending": pending,
        "high_critical": int(high_critical or 0),
        "sla_breached": sum(1 for c in unresolved if _sla_state(c, db) == "Breached"),
        "at_risk": sum(1 for c in unresolved if _sla_state(c, db) == "At Risk"),
        "unassigned": sum(1 for c in unresolved if c.status == "Assigned" and c.complaint_id not in assigned_ids),
    }

@router.get("/complaints")
def get_all_complaints(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    assignments = {a.complaint_id:a.officer_id for a in db.query(ComplaintAssignment).all()}
    officer_ids = set(assignments.values())
    names = {u.user_id:u.full_name for u in db.query(User).filter(User.user_id.in_(officer_ids)).all()} if officer_ids else {}
    return [{
        "complaint_id":c.complaint_id, "title":display_operational_title(c.translated_title or c.title, c.predicted_department, c.translated_text or c.description), "state":c.state, "district":c.district,
        "department":c.predicted_department, "priority":c.priority, "status":c.status,
        "latitude": c.latitude, "longitude": c.longitude, "area": c.translated_area or c.area, "address": c.translated_address or c.address, "landmark": c.translated_landmark or c.landmark, "pincode": c.pincode, "location_source": c.location_source,
        "display_status": complaint_display_status(c.status, c.complaint_id in assignments),
        "created_at":c.created_at, "assignee":names.get(assignments.get(c.complaint_id)),
        "sla_state": _sla_state(c, db)
    } for c in rows]


@router.delete("/complaints/{complaint_id}")
def delete_complaint(
    complaint_id: int,
    payload: ComplaintDeleteRequest,
    admin: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    cluster_id = complaint.incident_cluster_id or complaint.complaint_id
    media_files = [complaint.media_path, complaint.resolution_proof_path]
    db.add(ComplaintDeletion(
        complaint_id=complaint.complaint_id,
        deleted_by=str(admin.get("sub") or "admin"),
        reason=payload.reason.strip(),
    ))

    # Keep dependent history and references from blocking the physical delete.
    db.query(InAppNotification).filter(InAppNotification.complaint_id == complaint_id).update(
        {InAppNotification.complaint_id: None}, synchronize_session=False
    )
    db.query(Complaint).filter(Complaint.duplicate_of_id == complaint_id).update(
        {Complaint.duplicate_of_id: None}, synchronize_session=False
    )
    db.query(Complaint).filter(Complaint.duplicate_match_id == complaint_id).update(
        {Complaint.duplicate_match_id: None}, synchronize_session=False
    )
    db.query(ComplaintAssignment).filter(ComplaintAssignment.complaint_id == complaint_id).delete(synchronize_session=False)
    db.query(ComplaintEscalation).filter(ComplaintEscalation.complaint_id == complaint_id).delete(synchronize_session=False)
    db.query(ComplaintEvent).filter(ComplaintEvent.complaint_id == complaint_id).delete(synchronize_session=False)
    db.query(Feedback).filter(Feedback.complaint_id == complaint_id).update(
        {Feedback.complaint_id: None}, synchronize_session=False
    )
    db.query(TranslationFeedback).filter(TranslationFeedback.complaint_id == complaint_id).delete(synchronize_session=False)
    remaining_cluster_reports = db.query(Complaint.complaint_id).filter(
        Complaint.complaint_id != complaint_id,
        Complaint.incident_cluster_id == cluster_id,
    ).first()
    if not remaining_cluster_reports:
        db.query(ComplaintSupport).filter(ComplaintSupport.incident_cluster_id == cluster_id).delete(synchronize_session=False)

    db.delete(complaint)
    # Recalculate open cases in the affected incident so the removed report no
    # longer contributes to their community-count priority signal.
    remaining_cluster_cases = db.query(Complaint).filter(
        Complaint.incident_cluster_id == cluster_id,
        Complaint.status != "Resolved",
    ).all()
    if remaining_cluster_cases:
        refresh_priorities(db, remaining_cluster_cases, commit=False)
    db.commit()

    upload_root = os.path.abspath("uploads")
    for stored_path in media_files:
        if not stored_path:
            continue
        candidate = os.path.abspath(os.path.join(upload_root, os.path.basename(stored_path)))
        if os.path.dirname(candidate) == upload_root and os.path.isfile(candidate):
            try:
                os.remove(candidate)
            except OSError:
                pass
    return {"message": "Complaint deleted. A minimal admin audit record was retained.", "complaint_id": complaint_id}

@router.get("/departments")
def department_performance(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    departments = db.query(Department).order_by(Department.department_name).all()
    if not departments:
        return []

    complaints = db.query(Complaint).all()
    officers = db.query(User).filter(func.lower(User.role) == "officer").all()
    complaints_by_department = {d.department_id: [] for d in departments}
    officers_by_department = {d.department_id: [] for d in departments}
    for complaint in complaints:
        complaints_by_department.setdefault(complaint.department_id, []).append(complaint)
    for officer in officers:
        officers_by_department.setdefault(officer.department_id, []).append(officer)

    result = []
    for d in departments:
        cs = complaints_by_department.get(d.department_id, [])
        unresolved = [c for c in cs if c.status != "Resolved"]
        dept_officers = officers_by_department.get(d.department_id, [])
        result.append({
            "department_id": d.department_id,
            "department_name": d.department_name,
            "department_code": getattr(d, "department_code", None),
            "head_name": getattr(d, "head_name", None),
            "department_email": d.department_email,
            "state": getattr(d, "state", None),
            "jurisdiction": getattr(d, "jurisdiction", None),
            "is_active": True if getattr(d, "is_active", None) is None else bool(d.is_active),
            "ai_supported": bool(getattr(d, "ai_supported", False)) or d.department_name.strip().lower() in AI_SUPPORTED_DEPARTMENTS,
            "total": len(cs),
            "resolved": sum(1 for c in cs if c.status == "Resolved"),
            "in_progress": sum(1 for c in cs if c.status == "In Progress"),
            "pending": sum(1 for c in cs if c.status not in {"Resolved", "In Progress"}),
            "sla_breached": sum(1 for c in unresolved if _sla_state(c, db) == "Breached"),
            "active_officers": sum(1 for o in dept_officers if o.is_active is not False),
        })
    return result

@router.get("/users")
def users(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows=db.query(User).order_by(User.user_id.desc()).limit(250).all()
    return [{
        "user_id":u.user_id, "name":u.full_name, "email":u.email, "role":u.role,
        "state":u.state, "district":u.district, "department_id":u.department_id,
        "is_active": True if u.is_active is None else bool(u.is_active)
    } for u in rows]

@router.post("/departments")
def add_department(payload: DepartmentCreate, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    name = payload.department_name.strip()
    email = str(payload.department_email).strip().lower()
    username = payload.username.strip()
    if not name or not username or not payload.password:
        raise HTTPException(status_code=400, detail="Department name, username and password are required")
    if db.query(Department).filter(func.lower(Department.department_name) == name.lower()).first():
        raise HTTPException(status_code=409, detail="A department with this name already exists")
    if db.query(Department).filter((func.lower(Department.department_email) == email) | (func.lower(Department.username) == username.lower())).first():
        raise HTTPException(status_code=409, detail="Department email or username already exists")
    code = (payload.department_code or "").strip() or None
    if code and db.query(Department).filter(func.lower(Department.department_code) == code.lower()).first():
        raise HTTPException(status_code=409, detail="Department code already exists")
    ai_supported = name.lower() in AI_SUPPORTED_DEPARTMENTS
    d = Department(
        department_name=name, department_code=code, description=payload.description,
        head_name=payload.head_name.strip(), department_email=email, username=username,
        password=hash_password(payload.password), state=normalize_state(payload.state), jurisdiction=payload.jurisdiction,
        is_active=True, ai_supported=ai_supported
    )
    db.add(d); db.commit(); db.refresh(d)
    return {
        "message": "Department created successfully",
        "department_id": d.department_id,
        "ai_supported": ai_supported,
        "ai_note": "Supported by the current routing model" if ai_supported else "Operational department created; AI routing requires model retraining before automatic classification into this department."
    }

@router.get("/citizens")
def citizens(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).filter(func.lower(User.role) == "citizen").order_by(User.user_id.desc()).all()
    return [{
        "user_id":u.user_id, "name":u.full_name, "email":u.email, "phone":u.phone,
        "state":u.state, "district":u.district,
        "is_active": True if u.is_active is None else bool(u.is_active)
    } for u in rows]

@router.get("/officers")
def officers(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(User).filter(func.lower(User.role) == "officer").order_by(User.user_id.desc()).all()
    dept_ids={u.department_id for u in rows if u.department_id}
    depts={d.department_id:d.department_name for d in db.query(Department).filter(Department.department_id.in_(dept_ids)).all()} if dept_ids else {}
    metrics = officer_metrics_for_ids(db, [u.user_id for u in rows])
    return [{
        "user_id":u.user_id, "name":u.full_name, "email":u.email, "phone":u.phone,
        "department_id":u.department_id, "department":depts.get(u.department_id, "Unassigned"),
        "state":u.state, "district":u.district, "specialization":u.specialization,
        "max_active_cases":u.max_active_cases or 20,
        "is_active": True if u.is_active is None else bool(u.is_active),
        **metrics.get(u.user_id, {})
    } for u in rows]

@router.get("/department-heads")
def department_heads(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    rows=db.query(Department).order_by(Department.department_name).all()
    return [{
        "department_id":d.department_id, "department":d.department_name,
        "name":getattr(d,"head_name",None) or "Department Head", "email":d.department_email,
        "username":d.username, "state":getattr(d,"state",None),
        "is_active": True if getattr(d,"is_active",None) is None else bool(d.is_active)
    } for d in rows]



@router.get("/escalations")
def system_escalations(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    complaints = db.query(Complaint).all()
    refresh_priorities(db, complaints)
    sync_automatic_escalations(db, complaints)

    complaint_map = {c.complaint_id: c for c in complaints}
    dept_ids = {c.department_id for c in complaints if c.department_id}
    dept_map = {
        d.department_id: d.department_name
        for d in db.query(Department).filter(Department.department_id.in_(dept_ids)).all()
    } if dept_ids else {}

    rows = (
        db.query(ComplaintEscalation)
        .order_by(
            ComplaintEscalation.status.asc(),
            ComplaintEscalation.level.desc(),
            ComplaintEscalation.created_at.desc()
        )
        .limit(250)
        .all()
    )

    data = []
    for e in rows:
        c = complaint_map.get(e.complaint_id)
        if not c:
            continue
        data.append({
            "escalation_id": e.escalation_id,
            "complaint_id": e.complaint_id,
            "level": e.level,
            "reason": e.reason,
            "source": e.source,
            "status": e.status,
            "escalated_by": e.escalated_by,
            "created_at": e.created_at,
            "acknowledged_at": e.acknowledged_at,
            "resolved_at": e.resolved_at,
            "title": c.title,
            "priority": c.priority,
            "complaint_status": c.status,
            "department": dept_map.get(c.department_id, c.predicted_department or "Unknown"),
            "district": c.district,
            "state": c.state,
        })
    return data


@router.patch("/escalations/{escalation_id}/close")
def close_escalation(
    escalation_id: int,
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db)
):
    escalation = db.query(ComplaintEscalation).filter(
        ComplaintEscalation.escalation_id == escalation_id
    ).first()
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    escalation.status = "Closed"
    escalation.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Escalation closed"}


@router.get("/analytics/hotspots")
def geographic_hotspots(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Aggregate real complaint coordinates into small geographic cells.

    This is deliberately not a synthetic heatmap. A hotspot exists only where
    stored complaints contain latitude/longitude values.
    """
    complaints = (
        db.query(Complaint)
        .filter(
            Complaint.latitude.isnot(None),
            Complaint.longitude.isnot(None),
            Complaint.latitude != 0,
            Complaint.longitude != 0,
        )
        .all()
    )

    cells = {}
    for c in complaints:
        # Approx. 1 km cells in Indian latitudes; enough for an operational
        # hotspot view without pretending to have parcel-level precision.
        key = (round(float(c.latitude), 2), round(float(c.longitude), 2))
        cell = cells.setdefault(key, {
            "lat_sum": 0.0,
            "lon_sum": 0.0,
            "count": 0,
            "active": 0,
            "high_critical": 0,
            "incident_ids": set(),
            "districts": {},
            "states": {},
        })
        cell["lat_sum"] += float(c.latitude)
        cell["lon_sum"] += float(c.longitude)
        cell["count"] += 1
        cell["active"] += 1 if c.status != "Resolved" else 0
        cell["high_critical"] += 1 if c.priority in {"High", "Critical"} else 0
        cell["incident_ids"].add(c.incident_cluster_id or c.complaint_id)
        if c.district:
            cell["districts"][c.district] = cell["districts"].get(c.district, 0) + 1
        if c.state:
            cell["states"][c.state] = cell["states"].get(c.state, 0) + 1

    result = []
    for cell in cells.values():
        count = cell["count"]
        district = max(cell["districts"], key=cell["districts"].get) if cell["districts"] else None
        state = max(cell["states"], key=cell["states"].get) if cell["states"] else None
        # District is currently user/record supplied; coordinates are not checked
        # against an administrative-boundary dataset. Flag mixed labels rather than
        # silently presenting a majority label as geographically verified.
        district_labels = sorted(cell["districts"].keys())
        district_data_warning = (
            "Conflicting district labels in this map cell; verify complaint location data."
            if len(district_labels) > 1 else
            "District comes from complaint records and has not been verified against boundary polygons."
            if district else "District not supplied; verify location."
        )
        high_ratio = cell["high_critical"] / max(1, count)
        active_ratio = cell["active"] / max(1, count)

        # Transparent cell-level severity rule:
        # High: 5+ complaints, OR 2+ high/critical complaints and >=50% high/critical.
        # Medium: 3-4 complaints, OR at least one high/critical complaint.
        # Low: fewer than 3 complaints and no high/critical complaints.
        if count >= 5 or (cell["high_critical"] >= 2 and high_ratio >= 0.5):
            level = "High"
        elif count >= 3 or cell["high_critical"] >= 1:
            level = "Medium"
        else:
            level = "Low"

        result.append({
            "latitude": round(cell["lat_sum"] / count, 6),
            "longitude": round(cell["lon_sum"] / count, 6),
            "complaint_count": count,
            "active_count": cell["active"],
            "high_critical_count": cell["high_critical"],
            "incident_count": len(cell["incident_ids"]),
            "district": district,
            "area_label_type": "reported district label; not boundary-verified",
            "district_labels": district_labels,
            "district_data_warning": district_data_warning,
            "district_verified": False,
            "state": state,
            "hotspot_level": level,
            "severity_rule": "High: 5+ complaints OR 2+ high/critical and at least 50% high/critical; Medium: 3+ complaints OR at least 1 high/critical; Low: fewer than 3 and no high/critical.",
            "active_ratio": round(active_ratio, 2),
        })

    result.sort(key=lambda x: (-x["complaint_count"], -x["high_critical_count"]))
    return result[:150]




def _should_raise_surge_alert(reports_last_24h: int, critical_reports_last_24h: int) -> bool:
    """Transparent early-warning threshold; this is not an emergency diagnosis."""
    return reports_last_24h >= 3 or (reports_last_24h >= 2 and critical_reports_last_24h >= 1)


@router.get("/analytics/surge-alerts")
def emerging_incident_alerts(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Return clusters with a burst of recent reports for administrator triage."""
    now = datetime.now(timezone.utc)
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    clusters = {}
    for c in complaints:
        cluster_id = c.incident_cluster_id or c.complaint_id
        cell = clusters.setdefault(cluster_id, {
            "members": [], "recent": [],
            "latest": None,
        })
        cell["members"].append(c)
        created = c.created_at
        if created is not None:
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if now - timedelta(hours=24) <= created <= now + timedelta(minutes=5):
                cell["recent"].append(c)
                if cell["latest"] is None or created > cell["latest"]:
                    cell["latest"] = created

    from app.services.incident_alerts import (
        incident_burst_metrics, incident_alert_reason, should_raise_incident_alert,
    )

    alerts = []
    for cluster_id, cell in clusters.items():
        recent = cell["recent"]
        metrics = incident_burst_metrics(recent)
        if not should_raise_incident_alert(metrics):
            continue
        members = cell["members"]
        representative = recent[0]  # complaints were loaded newest-first
        unresolved = [c for c in members if c.status != "Resolved"]
        highest = metrics["highest_priority_last_24h"]
        reason = incident_alert_reason(metrics)
        located_recent = [c for c in recent if c.latitude is not None and c.longitude is not None and float(c.latitude) != 0 and float(c.longitude) != 0]
        alert_latitude = round(statistics.median(float(c.latitude) for c in located_recent), 6) if located_recent else None
        alert_longitude = round(statistics.median(float(c.longitude) for c in located_recent), 6) if located_recent else None
        alerts.append({
            "incident_cluster_id": cluster_id,
            "title": display_operational_title(representative.translated_title or representative.title, representative.predicted_department, representative.translated_text or representative.description),
            "department": representative.predicted_department or "Department not assigned",
            "district": representative.district,
            "state": representative.state,
            "latitude": alert_latitude,
            "longitude": alert_longitude,
            "location_available": bool(located_recent),
            "reports_last_24h": metrics["reports_last_24h"],
            "distinct_reporters_last_24h": metrics["distinct_reporters_last_24h"],
            "total_reports": len(members),
            "unresolved_reports": len(unresolved),
            "highest_priority": highest,
            "critical_reports_last_24h": metrics["critical_reports_last_24h"],
            "latest_report_at": cell["latest"],
            "alert_reason": reason,
        })
    alerts.sort(key=lambda a: (-a["distinct_reporters_last_24h"], -({"Critical":4,"High":3,"Medium":2,"Low":1}.get(a["highest_priority"],0)), -a["unresolved_reports"]))
    return alerts[:100]


def _admin_report_rows(db: Session):
    complaints = db.query(Complaint).order_by(Complaint.created_at.desc()).all()
    assignments = {a.complaint_id: a.officer_id for a in db.query(ComplaintAssignment).all()}
    officer_ids = {x for x in assignments.values() if x}
    officer_names = {
        u.user_id: u.full_name
        for u in db.query(User).filter(User.user_id.in_(officer_ids)).all()
    } if officer_ids else {}

    department_ids = {c.department_id for c in complaints if c.department_id}
    departments = {
        d.department_id: d.department_name
        for d in db.query(Department).filter(Department.department_id.in_(department_ids)).all()
    } if department_ids else {}

    rows = []
    for c in complaints:
        rows.append({
            "complaint_id": c.complaint_id,
            "title": display_operational_title(c.translated_title or c.title, c.predicted_department, c.translated_text or c.description),
            "state": c.state or "",
            "district": c.district or "",
            "department": departments.get(c.department_id, c.predicted_department or "Unassigned"),
            "priority": c.priority or "",
            "status": complaint_display_status(c, assignments.get(c.complaint_id)),
            "sla_state": _sla_state(c, db),
            "officer": officer_names.get(assignments.get(c.complaint_id), "Awaiting Officer"),
            "created_at": c.created_at.isoformat() if c.created_at else "",
        })
    return rows


@router.get("/integrations/bhashini")
def integration_bhashini_status(_: dict = Depends(require_admin)):
    """Non-secret translation-provider readiness for the Admin console."""
    from app.services.ai_service import bhashini_status, google_translate_status
    return {
        "bhashini": bhashini_status(),
        "google": google_translate_status(),
        # Backwards-compatible summary fields used by the existing Admin UI.
        **bhashini_status(),
    }


@router.get("/reports/complaints.csv")
def complaints_csv_report(
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = _admin_report_rows(db)
    stream = io.StringIO()
    fieldnames = [
        "complaint_id", "title", "state", "district", "department",
        "priority", "status", "sla_state", "officer", "created_at"
    ]
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

    filename = f"civicflow_complaints_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/complaints.pdf")
def complaints_pdf_report(
    _: dict = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = _admin_report_rows(db)

    # Matplotlib is already part of CivicFlow's project environment. Import it
    # lazily so normal API startup remains lightweight.
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    output = io.BytesIO()
    with PdfPages(output) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.06, 0.93, "CivicFlow AI — Administrative Grievance Report",
                 fontsize=18, fontweight="bold")
        fig.text(0.06, 0.895,
                 f"Generated: {datetime.now(timezone.utc).strftime('%d %b %Y, %H:%M UTC')}",
                 fontsize=9)
        total = len(rows)
        resolved = sum(1 for r in rows if r["status"] == "Resolved")
        breached = sum(1 for r in rows if r["sla_state"] == "Breached")
        high = sum(1 for r in rows if r["priority"] in {"High", "Critical"})
        fig.text(0.06, 0.83, f"Total complaints: {total}", fontsize=12)
        fig.text(0.30, 0.83, f"Resolved: {resolved}", fontsize=12)
        fig.text(0.50, 0.83, f"SLA breached: {breached}", fontsize=12)
        fig.text(0.72, 0.83, f"High/Critical: {high}", fontsize=12)

        by_department = {}
        for row in rows:
            by_department[row["department"]] = by_department.get(row["department"], 0) + 1
        ordered = sorted(by_department.items(), key=lambda x: (-x[1], x[0]))[:10]
        if ordered:
            labels = [x[0][:24] for x in ordered]
            values = [x[1] for x in ordered]
            ax = fig.add_axes([0.09, 0.12, 0.84, 0.58])
            ax.barh(labels[::-1], values[::-1])
            ax.set_title("Complaint Volume by Department", loc="left", fontsize=12)
            ax.set_xlabel("Complaints")
            ax.grid(axis="x", alpha=.2)
            for spine in ("top", "right"):
                ax.spines[spine].set_visible(False)
        else:
            fig.text(0.06, 0.68, "No complaint records are currently available.", fontsize=12)

        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)

        # Compact complaint register, 24 rows per page.
        columns = ["ID", "Title", "Department", "Priority", "Status", "SLA"]
        for offset in range(0, len(rows), 24):
            page_rows = rows[offset:offset + 24]
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            ax.axis("off")
            ax.set_title(
                f"Complaint Register — rows {offset + 1} to {offset + len(page_rows)}",
                loc="left", fontsize=14, fontweight="bold", pad=18
            )
            data = [[
                str(r["complaint_id"]),
                (r["title"] or "")[:38],
                (r["department"] or "")[:24],
                r["priority"],
                r["status"],
                r["sla_state"],
            ] for r in page_rows]
            table = ax.table(
                cellText=data,
                colLabels=columns,
                loc="upper center",
                cellLoc="left",
                colWidths=[.07, .31, .21, .11, .16, .14],
            )
            table.auto_set_font_size(False)
            table.set_fontsize(8)
            table.scale(1, 1.45)
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)

    output.seek(0)
    filename = f"civicflow_complaints_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.pdf"
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/analytics/status")
def complaint_status(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"label":r[0] or 'Unknown', "count":r[1]} for r in db.query(Complaint.status,func.count(Complaint.complaint_id)).group_by(Complaint.status).all()]

@router.get("/analytics/priority")
def complaint_priority(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"label":r[0] or 'Unknown', "count":r[1]} for r in db.query(Complaint.priority,func.count(Complaint.complaint_id)).group_by(Complaint.priority).all()]

@router.get("/analytics/department")
def complaints_department(_: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return [{"label":r[0] or 'Unknown', "count":r[1]} for r in db.query(Complaint.predicted_department,func.count(Complaint.complaint_id)).group_by(Complaint.predicted_department).all()]
