from fastapi import APIRouter, Depends, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, or_
from app.schemas.department_schema import (
    ComplaintStatusUpdate,
    OfficerActionCreate,
    OfficerCreate,
    OfficerProfileUpdate,
    OfficerStatusUpdate,
    DepartmentProfileUpdate,
    DepartmentPasswordChange,
    ManualRerouteRequest,
    ManualEscalationRequest
)
from fastapi import HTTPException
from app.database import get_db
from app.models.complaint import Complaint
from pydantic import BaseModel
from app.models.complaint_event import ComplaintEvent
from app.models.complaint_assignment import ComplaintAssignment
from app.models.user import User
from app.models.department import Department
from app.models.complaint_escalation import ComplaintEscalation
from app.models.contact import Feedback
from app.models.in_app_notification import InAppNotification
from app.models.translation_feedback import TranslationFeedback
from app.models.complaint_delay_request import ComplaintDelayRequest
from app.services.in_app_notifications import create_notification
from app.services.escalation_service import sync_automatic_escalations
from app.services.priority_engine import refresh_priorities, refresh_cluster, priority_breakdown
from app.services.officer_metrics import officer_metrics_for_ids
from app.services.sla_service import sla_info, assignment_deadline, ASSIGNMENT_HOURS, set_resolution_target
from app.utils.dependencies import get_current_department
from app.utils.security import hash_password, verify_password
from app.services.ai_service import (
    suggest_reroute_department, get_department_id, get_language_name, detect_language,
    translate_text, summarize_complaint, normalize_language_code,
    is_usable_english_translation
)
from app.utils.location_normalization import normalize_location
from app.services.incident_service import cluster_members, related_reason, incident_people_count, semantic_similar_complaints, semantic_match_explanation
from app.utils.workflow_status import complaint_display_status, assignee_display
from app.utils.complaint_titles import display_operational_title
from datetime import datetime, timezone, timedelta
import re
from app.utils.media import signed_media_url
import logging
import statistics

translation_logger = logging.getLogger("civicflow.translation")


class TranslationFeedbackReviewRequest(BaseModel):
    review_note: str | None = None


class OfficerDelayRequestPayload(BaseModel):
    reason: str
    blocker_category: str
    requested_until: datetime


class DelayRequestReviewPayload(BaseModel):
    decision: str
    note: str | None = None

router = APIRouter(prefix="/department", tags=["Department"])



def _ensure_operational_field_translations(complaint, db):
    """Fast read-path normalization.

    New complaints already store English operational copies at submission time.
    Read endpoints must never call an external translator because a dashboard
    page should not wait on network translation requests.

    For genuine English/unknown legacy rows we safely mirror the source fields.
    Multilingual legacy rows keep their stored translation if one exists.
    """
    language = normalize_language_code(complaint.language or "unknown")
    if language not in {"", "en", "english", "unknown"}:
        return False

    changed = False
    for source_attr, target_attr in (
        ("title", "translated_title"),
        ("area", "translated_area"),
        ("address", "translated_address"),
        ("landmark", "translated_landmark"),
    ):
        source = (getattr(complaint, source_attr, None) or "").strip()
        current = (getattr(complaint, target_attr, None) or "").strip()
        if source and not current:
            setattr(complaint, target_attr, source)
            changed = True

    if changed:
        db.commit()
    return changed


def _ensure_english_translation(complaint, db):
    """Return the best verified English processing copy for staff use.

    IMPORTANT: a previously verified translation is reused first. The translator
    is called only when the stored copy is missing/invalid. This avoids turning
    a valid complaint into "translation unavailable" during a temporary provider
    outage.
    """
    original = (complaint.description or "").strip()
    language = normalize_language_code(complaint.language or "unknown")

    # Do not trust legacy language metadata blindly.
    detected_from_text = detect_language(original)
    if language == "en" and detected_from_text not in {"en", "unknown"}:
        language = detected_from_text
        complaint.language = language

    # Genuine English complaints need no translation.
    if language == "en" and is_usable_english_translation(original, original):
        if complaint.translated_text != original:
            complaint.translated_text = original
            complaint.ai_summary = summarize_complaint(original)
            db.commit()
            db.refresh(complaint)
        return {"text": original, "status": "original_english", "repaired": True}

    # FIRST reuse a valid stored English translation. Do not re-contact Google
    # on every page load.
    stored = (complaint.translated_text or "").strip()
    if stored and is_usable_english_translation(original, stored):
        # Repair an old non-English summary if necessary.
        current_summary = (complaint.ai_summary or "").strip()
        if not current_summary or not is_usable_english_translation(original, current_summary):
            complaint.ai_summary = summarize_complaint(stored)
            db.commit()
            db.refresh(complaint)
        return {"text": stored, "status": "stored_translation", "repaired": False}

    # Production read path: never contact an external translation provider here.
    # Translation belongs to complaint ingestion / explicit repair jobs, not GET requests.
    return {
        "text": None,
        "status": "translation_missing",
        "repaired": False,
    }


def _actor_name(current_department):
    return getattr(current_department, "_actor_name", current_department.department_name)


def _actor_role(current_department):
    return getattr(current_department, "_actor_role", "manager")


def _actor_user_id(current_department):
    return getattr(current_department, "_actor_user_id", None)


def _assignment_for(complaint_id, db):
    return db.query(ComplaintAssignment).filter(ComplaintAssignment.complaint_id == complaint_id).first()


def _ensure_officer_can_access(complaint, current_department, db):
    if _actor_role(current_department) != "officer":
        return
    assignment = _assignment_for(complaint.complaint_id, db)
    if not assignment or assignment.officer_id != _actor_user_id(current_department):
        raise HTTPException(status_code=403, detail="This complaint is not assigned to your officer account")



def _duplicate_context(complaint, db):
    """Fast persisted incident lookup.

    Cluster membership is assigned at submission/backfill time, so opening a
    complaint no longer rebuilds an O(n²) similarity graph.
    """
    cluster = cluster_members(db, complaint, include_self=False)
    if not cluster:
        # Keep a stored possible match visible without making it a cluster.
        if complaint.duplicate_classification == "possible":
            return [], {
                "classification": "possible",
                "match_id": complaint.duplicate_match_id,
                "confidence": complaint.duplicate_confidence or 0.0,
                "similarity": complaint.duplicate_similarity or 0.0,
                "reason": complaint.duplicate_reason,
                "cluster_size": 1,
            }
        return [], None

    cluster_id = complaint.incident_cluster_id or complaint.complaint_id
    return cluster, {
        "classification": "high",
        "match_id": None,
        "confidence": 1.0,
        "similarity": 1.0,
        "cluster_size": len(cluster) + 1,
        "cluster_id": cluster_id,
        "reason": (
            f"Persisted incident #{cluster_id}: {len(cluster) + 1} reports are linked by "
            "high-confidence issue/locality matching. Membership is stored once, so every "
            "member shows the same group without rebuilding the cluster on page load."
        ),
    }


def _sla_info(complaint, db=None):
    return sla_info(complaint, db)

def _officer_brief(complaint, duplicate_group, sla):
    issue = complaint.ai_summary or complaint.description
    if len(issue) > 280:
        issue = issue[:277].rstrip() + "..."
    if complaint.status == "Assigned":
        next_action = "Acknowledge the complaint, verify field conditions and move it to In Progress when work begins."
    elif complaint.status == "In Progress":
        next_action = "Record the field action taken and resolve only after the issue has actually been addressed."
    else:
        next_action = "Keep the resolution evidence available for audit and citizen follow-up."
    if sla["state"] in ("At Risk", "Breached") and complaint.status != "Resolved":
        next_action = "SLA attention required: prioritize field action and record an accountable update."
    return {
        "issue": issue,
        "risk": (
            f"{complaint.priority} priority; SLA {sla['state']}; "
            f"priority confidence {round((complaint.priority_confidence or 0) * 100)}%"
        ),
        "duplicate_context": (f"{len(duplicate_group) + 1} reports are grouped around this incident." if duplicate_group else
                              (f"Possible related complaint #{complaint.duplicate_match_id} needs officer review." if complaint.duplicate_classification == "possible" else "No strong duplicate cluster detected.")),
        "next_action": next_action,
    }

@router.get("/dashboard")
def dashboard(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    query = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id
    )
    if _actor_role(current_department) == "officer":
        query = query.join(
            ComplaintAssignment,
            ComplaintAssignment.complaint_id == Complaint.complaint_id
        ).filter(ComplaintAssignment.officer_id == _actor_user_id(current_department))

    complaints = query.all()
    total = len(complaints)
    resolved = sum(1 for c in complaints if c.status == "Resolved")
    in_progress = sum(1 for c in complaints if c.status == "In Progress")
    pending = total - resolved
    high_priority = sum(1 for c in complaints if c.priority == "High")
    critical_priority = sum(1 for c in complaints if c.priority == "Critical")
    sla_states = [_sla_info(c, db)["state"] for c in complaints if c.status != "Resolved"]
    at_risk = sum(1 for state in sla_states if state == "At Risk")
    sla_breached = sum(1 for state in sla_states if state == "Breached")

    unassigned = 0
    active_officers = 0
    if _actor_role(current_department) == "manager":
        complaint_ids = [c.complaint_id for c in complaints if c.status != "Resolved"]
        assigned_ids = set()
        if complaint_ids:
            assigned_ids = {row[0] for row in db.query(ComplaintAssignment.complaint_id).filter(
                ComplaintAssignment.complaint_id.in_(complaint_ids)
            ).all()}
        # "Unassigned" means a complaint is waiting for an individual officer.
        # Legacy complaints that are already In Progress/Resolved pre-date officer
        # accountability and should not inflate the current assignment queue.
        unassigned = sum(
            1 for c in complaints
            if c.status == "Assigned" and c.complaint_id not in assigned_ids
        )
        active_officers = db.query(User).filter(
            User.department_id == current_department.department_id,
            func.lower(User.role) == "officer",
            User.is_active != False
        ).count()

    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "resolved": resolved,
        "high_priority": high_priority,
        "critical_priority": critical_priority,
        "at_risk": at_risk,
        "sla_breached": sla_breached,
        "unassigned": unassigned,
        "active_officers": active_officers,
        "viewer_role": _actor_role(current_department),
        "viewer_name": _actor_name(current_department),
    }


@router.get("/profile")
def get_department_profile(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        officer = db.query(User).filter(User.user_id == _actor_user_id(current_department)).first()
        if not officer:
            raise HTTPException(status_code=404, detail="Officer profile not found")
        active_cases = (
            db.query(ComplaintAssignment)
            .join(Complaint, Complaint.complaint_id == ComplaintAssignment.complaint_id)
            .filter(
                ComplaintAssignment.officer_id == officer.user_id,
                Complaint.status != "Resolved"
            ).count()
        )
        return {
            "viewer_role": "officer",
            "viewer_name": officer.full_name,
            "officer_name": officer.full_name,
            "officer_email": officer.email,
            "phone": officer.phone,
            "department_name": current_department.department_name,
            "department_email": current_department.department_email,
            "state": officer.state,
            "district": officer.district,
            "area": officer.area,
            "specialization": officer.specialization or "General",
            "max_active_cases": officer.max_active_cases or 20,
            "active_cases": active_cases,
            "is_active": officer.is_active is not False,
        }

    return {
        "department_name": current_department.department_name,
        "department_email": current_department.department_email,
        "username": current_department.username,
        "description": current_department.description,
        "viewer_role": "manager",
        "viewer_name": current_department.department_name
    }


@router.put("/profile")
def update_department_profile(
    profile: DepartmentProfileUpdate,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):

    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can edit the department profile")

    current_department.department_name = profile.department_name
    current_department.description = profile.description

    db.commit()

    return {
        "message": "Profile Updated Successfully"
    }


@router.put("/change-password")
def change_department_password(
    passwords: DepartmentPasswordChange,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        officer = db.query(User).filter(User.user_id == _actor_user_id(current_department)).first()
        if not officer or not verify_password(passwords.old_password, officer.password):
            raise HTTPException(status_code=400, detail="Old password is incorrect")
        officer.password = hash_password(passwords.new_password)
    else:
        if not verify_password(passwords.old_password, current_department.password):
            raise HTTPException(status_code=400, detail="Old password is incorrect")
        current_department.password = hash_password(passwords.new_password)

    db.commit()
    return {"message": "Password Changed Successfully"}


@router.get("/complaints")
def department_complaints(
    limit: int = 200, offset: int = 0,
    
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    
    query = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id
    )
    if _actor_role(current_department) == "officer":
        query = query.join(
            ComplaintAssignment,
            ComplaintAssignment.complaint_id == Complaint.complaint_id
        ).filter(ComplaintAssignment.officer_id == _actor_user_id(current_department))

    complaints = query.order_by(desc(Complaint.created_at)).offset(max(0, offset)).limit(max(1, min(limit, 1000))).all()

    data = []

    complaint_ids = [c.complaint_id for c in complaints]
    assignment_rows = (
        db.query(ComplaintAssignment.complaint_id, ComplaintAssignment.officer_id, User.full_name)
        .join(User, User.user_id == ComplaintAssignment.officer_id)
        .filter(ComplaintAssignment.complaint_id.in_(complaint_ids))
        .all() if complaint_ids else []
    )
    assignment_map = {row.complaint_id: {"officer_id": row.officer_id, "name": row.full_name} for row in assignment_rows}

    # Use persisted events rather than complaint.created_at to identify the
    # latest operational action (assignment, status change, reopening, etc.).
    latest_event_map = {}
    if complaint_ids:
        event_rows = (
            db.query(ComplaintEvent)
            .filter(
                ComplaintEvent.complaint_id.in_(complaint_ids),
                ComplaintEvent.actor == _actor_name(current_department),
            )
            .order_by(desc(ComplaintEvent.created_at), desc(ComplaintEvent.event_id))
            .all()
        )
        for event in event_rows:
            latest_event_map.setdefault(event.complaint_id, event)

    for c in complaints:
        assignment_info = assignment_map.get(c.complaint_id)
        latest_event = latest_event_map.get(c.complaint_id)
        data.append({
            "complaint_id": c.complaint_id,
            "title": display_operational_title(c.translated_title or c.title, c.predicted_department, c.translated_text or c.description),
            "latitude": c.latitude,
            "longitude": c.longitude,
            "area": c.translated_area or c.area,
            "address": c.translated_address or c.address,
            "landmark": c.translated_landmark or c.landmark,
            "pincode": c.pincode,
            "location_source": c.location_source,
            "district": c.district,
            "state": c.state,
            "priority": c.priority,
            "status": c.status,
            "display_status": complaint_display_status(c.status, bool(assignment_info), _actor_role(current_department)),
            "created_at": c.created_at,
            "latest_activity_title": latest_event.title if latest_event else None,
            "latest_activity_detail": latest_event.detail if latest_event else None,
            "latest_activity_actor": latest_event.actor if latest_event else None,
            "latest_activity_type": latest_event.event_type if latest_event else None,
            "latest_activity_at": latest_event.created_at if latest_event else None,
            "is_duplicate": c.is_duplicate,
            "sentiment": c.sentiment,
            "language": get_language_name(c.language),
            "assignee": assignee_display(assignment_info["name"] if assignment_info else None)
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

    _ensure_officer_can_access(complaint, current_department, db)
    assignment = _assignment_for(complaint.complaint_id, db)
    assigned_officer = db.query(User).filter(User.user_id == assignment.officer_id).first() if assignment else None

    # Keep the core View endpoint fast. Sentence-BERT matching is fetched
    # separately after the complaint page has already rendered.
    semantic_matches = []
    duplicate_group = []
    live_duplicate_analysis = None

    full_cluster_size = (
        db.query(Complaint)
        .filter(
            Complaint.incident_cluster_id
            == (complaint.incident_cluster_id or complaint.complaint_id)
        )
        .count()
    )

    sla = _sla_info(complaint, db)
    events = (
        db.query(ComplaintEvent)
        .filter(ComplaintEvent.complaint_id == complaint.complaint_id)
        .order_by(ComplaintEvent.created_at.desc())
        .all()
    )
    delay_requests = db.query(ComplaintDelayRequest).filter(
        ComplaintDelayRequest.complaint_id == complaint.complaint_id
    ).order_by(ComplaintDelayRequest.created_at.desc()).all()
    translation = _ensure_english_translation(complaint, db)
    translation_feedback_rows = db.query(TranslationFeedback).filter(
        TranslationFeedback.complaint_id == complaint.complaint_id
    ).order_by(TranslationFeedback.created_at.desc()).all()

    return {

        "complaint_id": complaint.complaint_id,

        "title": display_operational_title(complaint.translated_title or complaint.title, complaint.predicted_department, complaint.translated_text or complaint.description),
        "original_title": complaint.title,

        "description": complaint.description,
        "translated_text": translation["text"],
        "translation_status": translation["status"],
        "translation_feedback": [{
            "feedback_id": item.feedback_id,
            "citizen_id": item.citizen_id,
            "note": item.note,
            "suggested_english": item.suggested_english,
            "status": item.status,
            "reviewed_by": item.reviewed_by,
            "review_note": item.review_note,
            "created_at": item.created_at,
        } for item in translation_feedback_rows],

        "priority": complaint.priority,
        "department_confidence": complaint.department_confidence,
        "priority_confidence": complaint.priority_confidence,
        "priority_reason": complaint.priority_reason,

        "status": complaint.status,
        "display_status": complaint_display_status(complaint.status, bool(assignment), _actor_role(current_department)),

        "department": current_department.department_name,
        "assigned_officer": ({"user_id": assigned_officer.user_id, "name": assigned_officer.full_name, "email": assigned_officer.email} if assigned_officer else None),
        "viewer_role": _actor_role(current_department),
        "incident_scope": "officer" if _actor_role(current_department) == "officer" else "department",
        "incident_total_reports": full_cluster_size,

        "state": complaint.state,

        "district": complaint.district,

        "area": complaint.translated_area or complaint.area,
        "original_area": complaint.area,

        "address": complaint.translated_address or complaint.address,
        "original_address": complaint.address,

        "landmark": complaint.translated_landmark or complaint.landmark,
        "original_landmark": complaint.landmark,

        "pincode": complaint.pincode,

        "ai_summary": complaint.ai_summary,

        "language": get_language_name(complaint.language),

        "sentiment": complaint.sentiment,

        "is_duplicate": complaint.is_duplicate,

        "duplicate_of": complaint.duplicate_of_id,
        "duplicate_analysis": (
            {
                "classification": live_duplicate_analysis.get("classification", "none"),
                "match_id": live_duplicate_analysis.get("match_id"),
                "confidence": live_duplicate_analysis.get("confidence", 0.0),
                "text_similarity": live_duplicate_analysis.get("similarity", 0.0),
                "reason": live_duplicate_analysis.get("reason"),
                "cluster_size": live_duplicate_analysis.get("cluster_size"),
            }
            if live_duplicate_analysis else {
                "classification": complaint.duplicate_classification or "none",
                "match_id": complaint.duplicate_match_id,
                "confidence": complaint.duplicate_confidence or 0.0,
                "text_similarity": complaint.duplicate_similarity or 0.0,
                "reason": complaint.duplicate_reason,
                "cluster_size": None,
            }
        ),

        "incident_cluster_id": complaint.incident_cluster_id or complaint.complaint_id,
        "incident_affected_count": incident_people_count(db, complaint.incident_cluster_id or complaint.complaint_id),
        "duplicate_group": [
            {
                "complaint_id": item["complaint"].complaint_id,
                "title": display_operational_title(item["complaint"].translated_title or item["complaint"].title, item["complaint"].predicted_department, item["complaint"].translated_text or item["complaint"].description),
                "status": item["complaint"].status,
                "priority": item["complaint"].priority,
                "created_at": item["complaint"].created_at,
                "similarity": item["similarity"],
                "reason": semantic_match_explanation(
                    complaint,
                    item["complaint"],
                    item["similarity"],
                ) + " Location is excluded from this semantic match.",
            }
            for item in semantic_matches
        ],

        "media_url": signed_media_url(complaint.media_path),

        "created_at": complaint.created_at,

        "assigned_at": complaint.assigned_at,

        "in_progress_at": complaint.in_progress_at,

        "resolved_at": complaint.resolved_at,
        "resolution_proof_path": complaint.resolution_proof_path,
        "resolution_proof_url": signed_media_url(complaint.resolution_proof_path),
        "resolution_note": complaint.resolution_note,
        "citizen_resolution_status": complaint.citizen_resolution_status,
        "citizen_resolution_note": complaint.citizen_resolution_note,
        "sla": sla,
        "delay_requests": [{
            "request_id": item.request_id,
            "officer_id": item.officer_id,
            "reason": item.reason,
            "blocker_category": item.blocker_category,
            "requested_until": item.requested_until,
            "status": item.status,
            "manager_note": item.manager_note,
            "reviewed_by": item.reviewed_by,
            "reviewed_at": item.reviewed_at,
            "created_at": item.created_at,
        } for item in delay_requests],
        "officer_assignment_due_at": (
            complaint.officer_assignment_due_at
            or assignment_deadline(complaint.assigned_at or complaint.created_at, complaint.priority)
        ),
        "priority_analysis": priority_breakdown(complaint),
        "officer_brief": _officer_brief(complaint, duplicate_group, sla),
        "action_timeline": [
            {
                "event_id": e.event_id,
                "event_type": e.event_type,
                "title": e.title,
                "detail": e.detail,
                "actor": e.actor,
                "created_at": e.created_at,
            } for e in events
        ]

    }


@router.post("/complaint/{complaint_id}/translation-feedback/{feedback_id}/review")
def review_translation_feedback(
    complaint_id: int,
    feedback_id: int,
    payload: TranslationFeedbackReviewRequest,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    if _actor_role(current_department) != "manager":
        raise HTTPException(status_code=403, detail="Only the Department Head can close translation review requests")
    complaint = _get_own_complaint(complaint_id, current_department, db)
    item = db.query(TranslationFeedback).filter(
        TranslationFeedback.feedback_id == feedback_id,
        TranslationFeedback.complaint_id == complaint.complaint_id,
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Translation feedback not found")
    if item.status == "Reviewed":
        raise HTTPException(status_code=409, detail="This translation report has already been reviewed")

    item.status = "Reviewed"
    item.reviewed_by = _actor_name(current_department)
    item.review_note = (payload.review_note or "").strip() or None
    item.reviewed_at = datetime.now(timezone.utc)
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="translation_feedback_review",
        title="Department reviewed translation feedback",
        detail=item.review_note or "The Department Head reviewed the citizen's translation report. The processing copy remains unchanged until separately corrected.",
        actor=_actor_name(current_department),
    ))
    create_notification(
        db, notification_type="translation_feedback_reviewed",
        title="Department reviewed your translation feedback",
        message=f"The Department Head reviewed your translation feedback for complaint #{complaint.complaint_id}.",
        complaint_id=complaint.complaint_id, recipient_user_id=item.citizen_id,
        dedupe_key=f"translation-feedback-reviewed:{item.feedback_id}",
    )
    db.commit()
    return {"message": "Translation report reviewed. The original and processing text were preserved."}


@router.get("/complaint/{complaint_id}/semantic-matches")
def get_complaint_semantic_matches(
    complaint_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    """Heavy AI section loaded after the core complaint page is visible."""
    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.complaint_id == complaint_id,
            Complaint.department_id == current_department.department_id,
        )
        .first()
    )

    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")

    _ensure_officer_can_access(complaint, current_department, db)

    semantic_matches = semantic_similar_complaints(db, complaint)

    if _actor_role(current_department) == "officer" and semantic_matches:
        semantic_ids = [item["complaint"].complaint_id for item in semantic_matches]
        visible_ids = {
            row[0]
            for row in db.query(ComplaintAssignment.complaint_id)
            .filter(
                ComplaintAssignment.officer_id == _actor_user_id(current_department),
                ComplaintAssignment.complaint_id.in_(semantic_ids),
            )
            .all()
        }
        semantic_matches = [
            item for item in semantic_matches
            if item["complaint"].complaint_id in visible_ids
        ]

    top_similarity = semantic_matches[0]["similarity"] if semantic_matches else 0.0
    linked_incident_id = complaint.incident_cluster_id or complaint.complaint_id
    incident_report_count = db.query(Complaint.complaint_id).filter(
        Complaint.incident_cluster_id == linked_incident_id
    ).count()

    return {
        "incident_total_reports": incident_report_count or 1,
        "duplicate_analysis": (
            {
                "classification": "semantic",
                "match_id": semantic_matches[0]["complaint"].complaint_id,
                "confidence": top_similarity,
                "text_similarity": top_similarity,
                "cluster_size": len(semantic_matches) + 1,
                "reason": (
                    "Direct semantic matches from Sentence-BERT cosine similarity. "
                    "Similarity is pairwise, not transitive; location is not used."
                ),
            }
            if semantic_matches else {
                "classification": "none",
                "match_id": None,
                "confidence": 0.0,
                "text_similarity": 0.0,
                "cluster_size": 1,
                "reason": "No direct semantic match above the configured threshold.",
            }
        ),
        "duplicate_group": [
            {
                "complaint_id": item["complaint"].complaint_id,
                "title": display_operational_title(item["complaint"].translated_title or item["complaint"].title, item["complaint"].predicted_department, item["complaint"].translated_text or item["complaint"].description),
                "status": item["complaint"].status,
                "priority": item["complaint"].priority,
                "created_at": item["complaint"].created_at,
                "similarity": item["similarity"],
                "reason": semantic_match_explanation(
                    complaint,
                    item["complaint"],
                    item["similarity"],
                ) + " Location is excluded from this semantic match.",
            }
            for item in semantic_matches
        ],
    }

@router.put("/update-status/{complaint_id}")
def update_status(

    complaint_id: int,

    status_data: ComplaintStatusUpdate,

    current_department: Department = Depends(get_current_department),

    db: Session = Depends(get_db)

):

    if _actor_role(current_department) != "officer":
        raise HTTPException(status_code=403, detail="Complaint status is updated by the assigned officer. Department Heads manage assignment, rerouting and oversight.")

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

    _ensure_officer_can_access(complaint, current_department, db)

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

    if status_data.status == "Resolved" and not complaint.resolution_proof_path:
        raise HTTPException(
            status_code=400,
            detail="Upload resolution proof and a resolution note before marking this complaint Resolved"
        )

    now = datetime.now(timezone.utc)

    complaint.status = status_data.status

    if status_data.status == "In Progress":

        complaint.in_progress_at = now

    elif status_data.status == "Resolved":

        complaint.resolved_at = now

    # Status changes are complaint-specific. Duplicate grouping is advisory
    # and must not silently resolve another citizen's report.
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="status",
        title=f"Status changed to {status_data.status}",
        detail=status_data.note or "Status updated by department officer.",
        actor=_actor_name(current_department)
    ))

    db.commit()
    db.refresh(complaint)
    refresh_priorities(db, [complaint])

    return {"message": "Status Updated Successfully"}






@router.post("/complaint/{complaint_id}/resolution-proof")
async def upload_resolution_proof(
    complaint_id: int,
    note: str = Form(...),
    proof: UploadFile = File(...),
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) != "officer":
        raise HTTPException(status_code=403, detail="Only the assigned officer can upload resolution proof")
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.department_id == current_department.department_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_officer_can_access(complaint, current_department, db)
    if not proof.content_type or not proof.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Resolution proof must be an image")
    import os, uuid
    from io import BytesIO
    from PIL import Image, UnidentifiedImageError
    max_bytes = 15 * 1024 * 1024
    data = await proof.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail="Resolution proof is too large (max 15 MB)")
    # Trust the real image format, never the client-supplied filename/extension.
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = img.format
            if fmt not in {"JPEG", "PNG"} or img.width * img.height > 24_000_000:
                raise ValueError("unsupported")
            img.verify()
    except (UnidentifiedImageError, ValueError, OSError):
        raise HTTPException(status_code=400, detail="Resolution proof must be a genuine JPG/PNG image up to 24 megapixels")
    ext = ".png" if fmt == "PNG" else ".jpg"
    filename = f"resolution_{complaint_id}_{uuid.uuid4().hex}{ext}"
    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", filename)
    with open(path, "wb") as f:
        f.write(data)
    complaint.resolution_proof_path = filename
    complaint.resolution_note = note.strip()
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id, event_type="resolution_proof",
        title="Resolution proof uploaded", detail=complaint.resolution_note, actor=_actor_name(current_department)
    ))
    db.commit()
    return {"message": "Resolution proof uploaded successfully", "proof_url": "/" + signed_media_url(filename)}


def _get_own_complaint(complaint_id, current_department, db):
    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.complaint_id == complaint_id,
            Complaint.department_id == current_department.department_id
        )
        .first()
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    _ensure_officer_can_access(complaint, current_department, db)
    return complaint


@router.get("/available-departments")
def get_available_departments(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) != "manager":
        raise HTTPException(status_code=403, detail="Only the Department Head can view transfer destinations")
    rows = (
        db.query(Department)
        .filter(Department.is_active.is_(True))
        .order_by(Department.department_name)
        .all()
    )
    return [
        {
            "department_id": d.department_id,
            "department_name": d.department_name,
            "ai_supported": bool(d.ai_supported),
        }
        for d in rows
        if d.department_id != current_department.department_id
    ]


@router.put("/complaint/{complaint_id}/manual-reroute")
def manual_reroute(
    complaint_id: int,
    payload: ManualRerouteRequest,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) != "manager":
        raise HTTPException(status_code=403, detail="Only the Department Head can manually transfer complaints")
    complaint = _get_own_complaint(complaint_id, current_department, db)
    target = db.query(Department).filter(
        Department.department_id == payload.department_id,
        Department.is_active.is_(True)
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target department not found or inactive")
    if target.department_id == current_department.department_id:
        raise HTTPException(status_code=400, detail="Complaint is already in this department")

    old_department = current_department.department_name
    old_assignment = _assignment_for(complaint.complaint_id, db)
    old_officer_id = old_assignment.officer_id if old_assignment else None
    if old_assignment:
        db.delete(old_assignment)

    complaint.department_id = target.department_id
    complaint.status = "Assigned"
    complaint.assigned_at = datetime.now(timezone.utc)
    complaint.officer_assignment_due_at = assignment_deadline(complaint.assigned_at, complaint.priority)
    reason = (payload.reason or "Department Head manually corrected the routing destination.").strip()
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="manual_reroute",
        title=f"Transferred to {target.department_name}",
        detail=f"Moved from {old_department}. {reason}" + (f" Previous officer assignment {old_officer_id} was cleared." if old_officer_id else ""),
        actor=_actor_name(current_department),
    ))
    db.commit()
    return {
        "message": f"Complaint transferred from {old_department} to {target.department_name}",
        "complaint_id": complaint.complaint_id,
        "new_department_id": target.department_id,
        "new_department": target.department_name,
        "assignment_cleared": bool(old_assignment),
    }


@router.get("/complaint/{complaint_id}/reroute-suggestion")
def get_reroute_suggestion(
    complaint_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) != "manager":
        raise HTTPException(status_code=403, detail="Only the Department Head can review or apply rerouting decisions")
    complaint = _get_own_complaint(complaint_id, current_department, db)

    translation = _ensure_english_translation(complaint, db)
    complaint_text = translation["text"]
    if not complaint_text:
        raise HTTPException(
            status_code=409,
            detail="English translation is unavailable. Select/correct the complaint language before requesting an AI reroute."
        )

    suggestion = suggest_reroute_department(
        complaint_text,
        current_department.department_name
    )

    return {
        "complaint_id": complaint.complaint_id,
        "current_department": current_department.department_name,
        "reroute_required": suggestion["reroute_required"],
        "suggested_department": suggestion["suggested_department"],
        "reason": suggestion["reason"]
    }


@router.put("/complaint/{complaint_id}/reroute")
def apply_reroute(
    complaint_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) != "manager":
        raise HTTPException(status_code=403, detail="Only the Department Head can review or apply rerouting decisions")
    complaint = _get_own_complaint(complaint_id, current_department, db)

    translation = _ensure_english_translation(complaint, db)
    complaint_text = translation["text"]
    if not complaint_text:
        raise HTTPException(
            status_code=409,
            detail="English translation is unavailable. Rerouting was not applied."
        )

    suggestion = suggest_reroute_department(
        complaint_text,
        current_department.department_name
    )

    if not suggestion["reroute_required"]:
        raise HTTPException(
            status_code=400,
            detail="No reroute is suggested for this complaint"
        )

    new_department_id = get_department_id(suggestion["suggested_department"], db)
    if new_department_id is None:
        raise HTTPException(
            status_code=409,
            detail=f"The suggested {suggestion['suggested_department']} department is not configured or active. No changes were made.",
        )

    old_department_name = current_department.department_name
    complaint.department_id = new_department_id
    complaint.status = "Assigned"
    complaint.assigned_at = datetime.now(timezone.utc)
    existing_assignment = _assignment_for(complaint.complaint_id, db)
    if existing_assignment:
        db.delete(existing_assignment)
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="reroute",
        title=f"Rerouted to {suggestion['suggested_department']}",
        detail=f"Moved from {old_department_name}. {suggestion['reason']}",
        actor=_actor_name(current_department)
    ))

    db.commit()
    db.refresh(complaint)

    return {
        "message": f"Complaint rerouted to {suggestion['suggested_department']}",
        "complaint_id": complaint.complaint_id,
        "new_department_id": new_department_id
    }

@router.post("/complaint/{complaint_id}/action")
def add_officer_action(
    complaint_id: int,
    action: OfficerActionCreate,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) != "officer":
        raise HTTPException(status_code=403, detail="Operational action notes are recorded by the assigned officer")
    complaint = _get_own_complaint(complaint_id, current_department, db)
    note = action.note.strip()
    if not note:
        raise HTTPException(status_code=400, detail="Action note cannot be empty")
    event = ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="officer_action",
        title=(action.action_type or "Officer Note")[:160],
        detail=note,
        actor=_actor_name(current_department)
    )
    db.add(event)
    db.commit()
    return {"message": "Action recorded in audit timeline"}


@router.post("/complaint/{complaint_id}/delay-request")
def request_officer_delay(
    complaint_id: int,
    payload: OfficerDelayRequestPayload,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    """Let the assigned officer request a reasoned, time-bounded extension."""
    if _actor_role(current_department) != "officer":
        raise HTTPException(status_code=403, detail="Only the assigned officer can request more time")
    complaint = _get_own_complaint(complaint_id, current_department, db)
    if complaint.status == "Resolved":
        raise HTTPException(status_code=400, detail="A resolved complaint cannot request an extension")
    now = datetime.now(timezone.utc)
    requested_until = payload.requested_until
    if requested_until.tzinfo is None:
        requested_until = requested_until.replace(tzinfo=timezone.utc)
    if requested_until <= now + timedelta(minutes=5):
        raise HTTPException(status_code=422, detail="Choose a follow-up time at least five minutes from now")
    if requested_until > now + timedelta(days=30):
        raise HTTPException(status_code=422, detail="A single delay request cannot exceed 30 days")
    reason = payload.reason.strip()
    if len(reason) < 12:
        raise HTTPException(status_code=422, detail="Explain the blocker and work already completed (at least 12 characters)")
    categories = {"parts", "equipment", "access", "weather", "safety", "utility_dependency", "staffing", "other"}
    category = payload.blocker_category.strip().lower()
    if category not in categories:
        raise HTTPException(status_code=422, detail="Select a valid delay reason")

    officer_id = _actor_user_id(current_department)
    pending_request = db.query(ComplaintDelayRequest).filter(
        ComplaintDelayRequest.complaint_id == complaint.complaint_id,
        ComplaintDelayRequest.status == "Pending Head Review",
    ).first()
    if pending_request:
        raise HTTPException(status_code=409, detail="A delay request is already waiting for the Department Head")
    request = ComplaintDelayRequest(
        complaint_id=complaint.complaint_id,
        officer_id=officer_id,
        reason=reason,
        blocker_category=category,
        requested_until=requested_until,
        status="Pending Head Review",
    )
    db.add(request)
    db.flush()
    # This concise decision brief is deliberately not an automated approval.
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="delay_request",
        title="Officer requested a revised work window",
        detail=(f"Blocker: {category.replace('_', ' ')}. Requested follow-up: "
                f"{requested_until.isoformat()}. Officer explanation: {reason}"),
        actor=_actor_name(current_department),
    ))
    create_notification(
        db, notification_type="officer_delay_review",
        title=f"Delay request needs review for complaint #{complaint.complaint_id}",
        message=(f"The officer reported a {category.replace('_', ' ')} blocker and requested until "
                 f"{requested_until.astimezone().strftime('%d %b %Y, %I:%M %p')}. "
                 "Review the officer's explanation before approving or declining."),
        complaint_id=complaint.complaint_id,
        recipient_department_id=current_department.department_id,
        dedupe_key=f"officer-delay-review:{request.request_id}:head",
    )
    if complaint.citizen_id:
        create_notification(
            db, notification_type="officer_delay_requested",
            title="Your complaint has a reported work delay",
            message=(f"The officer reported a blocker and requested more time until "
                     f"{requested_until.astimezone().strftime('%d %b %Y, %I:%M %p')}. "
                     "The Department Head must review the request; the original target remains recorded."),
            complaint_id=complaint.complaint_id,
            recipient_user_id=complaint.citizen_id,
            dedupe_key=f"officer-delay-requested:{request.request_id}:citizen",
        )
    db.commit()
    return {
        "message": "Delay request sent to the Department Head. It is not approved until the Head reviews it.",
        "request_id": request.request_id,
        "decision_support": "Review the blocker, work completed, safety impact and requested follow-up time. CivicFlow does not approve extensions automatically.",
    }


@router.put("/complaint/{complaint_id}/delay-request/{request_id}")
def review_officer_delay_request(
    complaint_id: int,
    request_id: int,
    payload: DelayRequestReviewPayload,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    if _actor_role(current_department) != "manager":
        raise HTTPException(status_code=403, detail="Only the Department Head can decide a delay request")
    complaint = _get_own_complaint(complaint_id, current_department, db)
    request = db.query(ComplaintDelayRequest).filter(
        ComplaintDelayRequest.request_id == request_id,
        ComplaintDelayRequest.complaint_id == complaint.complaint_id,
    ).first()
    if request is None:
        raise HTTPException(status_code=404, detail="Delay request not found")
    if request.status != "Pending Head Review":
        raise HTTPException(status_code=409, detail="This delay request has already been reviewed")
    decision = payload.decision.strip().lower()
    if decision not in {"approve", "decline"}:
        raise HTTPException(status_code=422, detail="Decision must be approve or decline")
    note = (payload.note or "").strip()
    if decision == "decline" and len(note) < 5:
        raise HTTPException(status_code=422, detail="Add a short reason when declining the request")

    request.status = "Approved" if decision == "approve" else "Declined"
    request.manager_note = note or None
    request.reviewed_by = _actor_name(current_department)
    request.reviewed_at = datetime.now(timezone.utc)
    approved = decision == "approve"
    db.add(ComplaintEvent(
        complaint_id=complaint.complaint_id,
        event_type="delay_review",
        title=f"Department Head {request.status.lower()} the delay request",
        detail=(note or "The requested follow-up window was approved.") +
               (f" Follow-up due: {request.requested_until.isoformat()}." if approved else ""),
        actor=_actor_name(current_department),
    ))
    officer = db.query(User).filter(User.user_id == request.officer_id).first()
    if officer:
        create_notification(
            db, notification_type="officer_delay_decision",
            title=f"Delay request {request.status.lower()}",
            message=(f"The Department Head {request.status.lower()} your request for complaint #{complaint.complaint_id}. "
                     + (f"Follow-up is due at {request.requested_until.astimezone().strftime('%d %b %Y, %I:%M %p')}." if approved else note)),
            complaint_id=complaint.complaint_id,
            recipient_user_id=officer.user_id,
            dedupe_key=f"officer-delay-decision:{request.request_id}:officer",
        )
    if complaint.citizen_id:
        create_notification(
            db, notification_type="citizen_delay_decision",
            title="Department reviewed the reported delay",
            message=(f"The Department Head {request.status.lower()} the officer's request for your complaint. "
                     + (f"The next follow-up is expected by {request.requested_until.astimezone().strftime('%d %b %Y, %I:%M %p')}." if approved else "The original service target remains in effect.")),
            complaint_id=complaint.complaint_id,
            recipient_user_id=complaint.citizen_id,
            dedupe_key=f"officer-delay-decision:{request.request_id}:citizen",
        )
    db.commit()
    return {"message": f"Delay request {request.status.lower()}.", "status": request.status}


@router.get("/emerging-incident-alerts")
def department_emerging_incident_alerts(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    """Show surge alerts directly to the department responsible for the complaints.

    Department managers see their department's clusters without waiting for an
    administrator to forward an alert. Officers see only alerts involving their
    own assigned complaints, to keep the response actionable.
    """
    role = _actor_role(current_department)
    query = db.query(Complaint).filter(Complaint.department_id == current_department.department_id)
    if role == "officer":
        actor_user_id = _actor_user_id(current_department)
        query = query.join(ComplaintAssignment, ComplaintAssignment.complaint_id == Complaint.complaint_id).filter(
            ComplaintAssignment.officer_id == actor_user_id
        )
    complaints = query.order_by(Complaint.created_at.desc()).all()
    now = datetime.now(timezone.utc)
    clusters = {}
    for c in complaints:
        cluster_id = c.incident_cluster_id or c.complaint_id
        cell = clusters.setdefault(cluster_id, {"members": [], "recent": [], "latest": None})
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
    priority_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    for cluster_id, cell in clusters.items():
        recent = cell["recent"]
        metrics = incident_burst_metrics(recent)
        if not should_raise_incident_alert(metrics):
            continue
        members = cell["members"]
        representative = recent[0]
        unresolved = [c for c in members if (c.status or "").lower() != "resolved"]
        highest = metrics["highest_priority_last_24h"]
        reason = incident_alert_reason(metrics)
        located_recent = [c for c in recent if c.latitude is not None and c.longitude is not None and float(c.latitude) != 0 and float(c.longitude) != 0]
        alert_latitude = round(statistics.median(float(c.latitude) for c in located_recent), 6) if located_recent else None
        alert_longitude = round(statistics.median(float(c.longitude) for c in located_recent), 6) if located_recent else None
        alerts.append({
            "incident_cluster_id": cluster_id,
            "title": display_operational_title(representative.translated_title or representative.title, representative.predicted_department, representative.translated_text or representative.description),
            "department": current_department.department_name,
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
    alerts.sort(key=lambda a: (-a["distinct_reporters_last_24h"], -(priority_rank.get((a["highest_priority"] or "").lower(), 0)), -a["unresolved_reports"]))
    return {"department": current_department.department_name, "viewer_role": role, "alerts": alerts[:100]}


@router.get("/notifications")
def department_notifications(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    """Persistent in-app inbox. SLA stage notifications are created once per stage.

    Officers only see their own items. Department managers see department-wide items.
    """
    role = _actor_role(current_department)
    actor_user_id = _actor_user_id(current_department)

    # Materialize current SLA transitions as persistent, deduplicated inbox items.
    sla_query = db.query(Complaint).filter(
        Complaint.department_id == current_department.department_id,
        Complaint.status != "Resolved"
    )
    if role == "officer":
        sla_query = sla_query.join(
            ComplaintAssignment,
            ComplaintAssignment.complaint_id == Complaint.complaint_id
        ).filter(ComplaintAssignment.officer_id == actor_user_id)

    for complaint in sla_query.all():
        sla = _sla_info(complaint, db)
        if sla["state"] not in {"At Risk", "Breached"}:
            continue
        state = sla["state"]
        remaining = sla.get("remaining_minutes")
        if state == "Breached":
            overdue = abs(remaining or 0)
            message = f"Complaint #{complaint.complaint_id} breached its SLA by {overdue // 60}h {overdue % 60}m. Record action or escalate immediately."
            ntype = "sla_breached"
        else:
            message = f"Complaint #{complaint.complaint_id} is approaching its SLA deadline. Please record progress before the deadline."
            ntype = "sla_at_risk"
        assignment = _assignment_for(complaint.complaint_id, db)
        # Department managers receive a department-wide copy.
        create_notification(
            db, notification_type=ntype, title=f"SLA {state}: complaint #{complaint.complaint_id}",
            message=message, complaint_id=complaint.complaint_id,
            recipient_department_id=current_department.department_id,
            dedupe_key=f"sla:{complaint.complaint_id}:{state.lower().replace(' ', '-')}:dept:{current_department.department_id}"
        )
        if assignment:
            create_notification(
                db, notification_type=ntype, title=f"SLA {state}: complaint #{complaint.complaint_id}",
                message=message, complaint_id=complaint.complaint_id,
                recipient_user_id=assignment.officer_id,
                dedupe_key=f"sla:{complaint.complaint_id}:{state.lower().replace(' ', '-')}:user:{assignment.officer_id}"
            )
    db.commit()

    if role == "officer":
        query = db.query(InAppNotification).filter(InAppNotification.recipient_user_id == actor_user_id)
    else:
        query = db.query(InAppNotification).filter(
            InAppNotification.recipient_department_id == current_department.department_id,
            InAppNotification.recipient_user_id.is_(None),
        )

    total = query.count()
    unread_count = query.filter(InAppNotification.read_at.is_(None)).count()
    rows = query.order_by(InAppNotification.created_at.desc(), InAppNotification.notification_id.desc()).limit(30).all()
    complaint_ids = [row.complaint_id for row in rows if row.complaint_id]
    titles = {}
    if complaint_ids:
        titles = {c.complaint_id: (c.translated_title or c.title or f"Complaint #{c.complaint_id}")
                  for c in db.query(Complaint).filter(Complaint.complaint_id.in_(complaint_ids)).all()}

    notifications = []
    for row in rows:
        ctitle = titles.get(row.complaint_id, f"Complaint #{row.complaint_id}" if row.complaint_id else "CivicFlow update")
        notifications.append({
            "notification_id": row.notification_id,
            "type": row.notification_type,
            "title": row.title,
            "message": row.message,
            "complaint_id": row.complaint_id,
            "complaint_title": ctitle,
            "priority": None,
            "sla_state": "Breached" if row.notification_type == "sla_breached" else ("At Risk" if row.notification_type == "sla_at_risk" else None),
            "timestamp": row.created_at,
            "is_read": row.read_at is not None,
            "read_at": row.read_at,
        })
    return {
        "count": unread_count,
        "unread_count": unread_count,
        "total": total,
        "notifications": notifications,
    }


@router.patch("/notifications/{notification_id}/read")
def mark_department_notification_read(
    notification_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    role = _actor_role(current_department)
    query = db.query(InAppNotification).filter(InAppNotification.notification_id == notification_id)
    if role == "officer":
        query = query.filter(InAppNotification.recipient_user_id == _actor_user_id(current_department))
    else:
        query = query.filter(
            InAppNotification.recipient_department_id == current_department.department_id,
            InAppNotification.recipient_user_id.is_(None),
        )
    item = query.first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    if item.read_at is None:
        item.read_at = datetime.now(timezone.utc)
        db.commit()
    return {"message": "Notification marked as read", "notification_id": item.notification_id}


@router.patch("/notifications/read-all")
def mark_all_department_notifications_read(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    role = _actor_role(current_department)
    query = db.query(InAppNotification).filter(InAppNotification.read_at.is_(None))
    if role == "officer":
        query = query.filter(InAppNotification.recipient_user_id == _actor_user_id(current_department))
    else:
        query = query.filter(
            InAppNotification.recipient_department_id == current_department.department_id,
            InAppNotification.recipient_user_id.is_(None),
        )
    changed = query.update({InAppNotification.read_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    return {"message": "Notifications marked as read", "updated": changed}



@router.get("/escalations")
def department_escalations(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can view the escalation queue")

    complaints = (
        db.query(Complaint)
        .filter(Complaint.department_id == current_department.department_id)
        .all()
    )
    refresh_priorities(db, complaints)   # keep priority live before SLA/escalation checks
    sync_automatic_escalations(db, complaints)

    complaint_ids = [c.complaint_id for c in complaints]
    if not complaint_ids:
        return []

    complaint_map = {c.complaint_id: c for c in complaints}
    rows = (
        db.query(ComplaintEscalation)
        .filter(ComplaintEscalation.complaint_id.in_(complaint_ids))
        .order_by(
            ComplaintEscalation.status.asc(),
            ComplaintEscalation.level.desc(),
            ComplaintEscalation.created_at.desc()
        )
        .all()
    )

    return [{
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
        "title": complaint_map[e.complaint_id].title,
        "priority": complaint_map[e.complaint_id].priority,
        "complaint_status": complaint_map[e.complaint_id].status,
        "district": complaint_map[e.complaint_id].district,
    } for e in rows]


class EmergencyAlertRequest(BaseModel):
    verified: bool = True
    note: str | None = None


@router.post("/complaint/{complaint_id}/emergency-alert")
def set_verified_emergency(
    complaint_id: int,
    payload: EmergencyAlertRequest,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    """Manager marks (or clears) a verified emergency alert for the location."""
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can verify an emergency alert")
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.department_id == current_department.department_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.status == "Resolved":
        raise HTTPException(status_code=400, detail="Resolved complaints cannot carry an emergency alert")
    complaint.verified_emergency = bool(payload.verified)
    db.add(ComplaintEvent(
        complaint_id=complaint_id, event_type="emergency_alert",
        title="Verified emergency alert " + ("set" if payload.verified else "cleared"),
        detail=(payload.note or "").strip() or None,
        actor=_actor_name(current_department),
    ))
    db.commit()
    refresh_cluster(db, complaint)
    return {"message": "Emergency alert updated", "priority": complaint.priority,
            "priority_analysis": priority_breakdown(complaint)}


@router.post("/complaint/{complaint_id}/escalate")
def manually_escalate_complaint(
    complaint_id: int,
    payload: ManualEscalationRequest,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can escalate complaints")

    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.department_id == current_department.department_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    if complaint.status == "Resolved":
        raise HTTPException(status_code=400, detail="Resolved complaints do not need escalation")

    level = max(1, min(int(payload.level or 2), 3))
    reason = (payload.reason or "").strip()
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Provide a clear escalation reason")

    existing = db.query(ComplaintEscalation).filter(
        ComplaintEscalation.complaint_id == complaint_id,
        ComplaintEscalation.status.in_(["Open", "Acknowledged"])
    ).order_by(ComplaintEscalation.level.desc()).first()

    if existing:
        existing.level = max(existing.level, level)
        existing.reason = reason
        existing.source = "Manual"
        existing.status = "Open"
        existing.escalated_by = _actor_name(current_department)
        escalation = existing
    else:
        escalation = ComplaintEscalation(
            complaint_id=complaint_id,
            level=level,
            reason=reason,
            source="Manual",
            status="Open",
            escalated_by=_actor_name(current_department),
        )
        db.add(escalation)

    db.add(ComplaintEvent(
        complaint_id=complaint_id,
        event_type="escalation",
        title=f"Escalated to Level {level}",
        detail=reason,
        actor=_actor_name(current_department),
    ))
    db.commit()
    db.refresh(escalation)

    return {
        "message": f"Complaint escalated to Level {level}",
        "escalation_id": escalation.escalation_id,
        "level": escalation.level,
    }


@router.patch("/escalations/{escalation_id}/acknowledge")
def acknowledge_escalation(
    escalation_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can acknowledge escalations")

    escalation = (
        db.query(ComplaintEscalation)
        .join(Complaint, Complaint.complaint_id == ComplaintEscalation.complaint_id)
        .filter(
            ComplaintEscalation.escalation_id == escalation_id,
            Complaint.department_id == current_department.department_id
        )
        .first()
    )
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    escalation.status = "Acknowledged"
    escalation.acknowledged_at = datetime.now(timezone.utc)
    db.commit()

    return {"message": "Escalation acknowledged"}




@router.get("/location-groups")
def department_location_groups(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    """Geographic workload hierarchy for Department Heads.

    Uses only real location fields stored with complaints:
    State -> District -> Area/Locality (pincode fallback) -> complaints.
    We intentionally do not label an area as an official 'block' because
    CivicFlow does not currently collect a verified block field.
    """
    if _actor_role(current_department) == "officer":
        raise HTTPException(
            status_code=403,
            detail="Location-group oversight is available to the Department Head.",
        )

    complaints = (
        db.query(Complaint)
        .filter(Complaint.department_id == current_department.department_id)
        .order_by(Complaint.created_at.desc())
        .all()
    )

    districts = {}
    for complaint in complaints:

        district_name = (complaint.district or "District not specified").strip()
        state_name = (complaint.state or "State not specified").strip()

        district_key = f"{state_name.lower()}::{district_name.lower()}"
        district = districts.setdefault(
            district_key,
            {
                "state": state_name,
                "district": district_name,
                "total": 0,
                "active": 0,
                "resolved": 0,
                "high_critical": 0,
                "areas": {},
            },
        )

        district["total"] += 1
        district["resolved"] += 1 if complaint.status == "Resolved" else 0
        district["active"] += 1 if complaint.status != "Resolved" else 0
        district["high_critical"] += (
            1 if complaint.priority in {"High", "Critical"} else 0
        )

        raw_area = (complaint.translated_area or complaint.area or "").strip()
        pincode = (complaint.pincode or "").strip()
        if raw_area:
            area_name = raw_area
        elif pincode:
            area_name = f"Pincode {pincode}"
        else:
            area_name = "Area not specified"

        area_key = area_name.lower()
        area = district["areas"].setdefault(
            area_key,
            {
                "area": area_name,
                "pincode": pincode or None,
                "total": 0,
                "active": 0,
                "resolved": 0,
                "high_critical": 0,
                "complaints": [],
            },
        )

        area["total"] += 1
        area["resolved"] += 1 if complaint.status == "Resolved" else 0
        area["active"] += 1 if complaint.status != "Resolved" else 0
        area["high_critical"] += (
            1 if complaint.priority in {"High", "Critical"} else 0
        )
        area["complaints"].append({
            "complaint_id": complaint.complaint_id,
            "title": display_operational_title(complaint.translated_title or complaint.title, complaint.predicted_department, complaint.translated_text or complaint.description),
            "status": complaint.status,
            "display_status": complaint_display_status(
                complaint.status,
                bool(_assignment_for(complaint.complaint_id, db)),
                "manager",
            ),
            "priority": complaint.priority,
            "address": complaint.translated_address or complaint.address,
            "landmark": complaint.translated_landmark or complaint.landmark,
            "pincode": complaint.pincode,
            "created_at": complaint.created_at,
        })

    result = []
    for district in districts.values():
        areas = list(district.pop("areas").values())
        areas.sort(key=lambda x: (-x["total"], x["area"].lower()))
        district["areas"] = areas
        district["area_count"] = len(areas)
        result.append(district)

    result.sort(key=lambda x: (-x["total"], x["district"].lower()))
    return {
        "department": current_department.department_name,
        "district_count": len(result),
        "total_complaints": len(complaints),
        "districts": result,
    }


@router.get("/officers")
def list_officers(
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    officers = db.query(User).filter(
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer"
    ).order_by(User.full_name).all()
    if not officers:
        return []

    officer_ids = [o.user_id for o in officers]
    rows = (
        db.query(ComplaintAssignment.officer_id, Complaint)
        .join(Complaint, Complaint.complaint_id == ComplaintAssignment.complaint_id)
        .filter(ComplaintAssignment.officer_id.in_(officer_ids))
        .all()
    )
    complaints_by_officer = {officer_id: [] for officer_id in officer_ids}
    for officer_id, complaint in rows:
        complaints_by_officer.setdefault(officer_id, []).append(complaint)

    metrics = officer_metrics_for_ids(db, officer_ids)

    result = []
    for officer in officers:
        complaints = complaints_by_officer.get(officer.user_id, [])
        unresolved = [c for c in complaints if c.status != "Resolved"]
        breached = sum(1 for c in unresolved if _sla_info(c, db)["state"] == "Breached")
        result.append({
            "user_id": officer.user_id,
            "name": officer.full_name,
            "email": officer.email,
            "phone": officer.phone,
            "state": officer.state,
            "district": officer.district,
            "area": officer.area,
            "specialization": officer.specialization or "General",
            "max_active_cases": officer.max_active_cases or 20,
            "is_active": True if officer.is_active is None else bool(officer.is_active),
            "active_cases": len(unresolved),
            "assigned": len(complaints),
            "pending": sum(1 for c in complaints if c.status == "Assigned"),
            "in_progress": sum(1 for c in complaints if c.status == "In Progress"),
            "resolved": sum(1 for c in complaints if c.status == "Resolved"),
            "sla_breached": breached,
            **metrics.get(officer.user_id, {}),
        })
    return result


@router.post("/officers")
def create_officer(
    officer: OfficerCreate,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can create officer accounts")

    full_name = (officer.full_name or "").strip()
    email = (officer.email or "").strip().lower()
    password = officer.password or ""
    if not full_name:
        raise HTTPException(status_code=422, detail="Officer name is required.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Enter a valid officer email address.")
    if len(password) < 8 or not password.strip():
        raise HTTPException(status_code=422, detail="Temporary password must contain at least 8 characters.")
    if db.query(User).filter(func.lower(User.email) == email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    phone = (officer.phone or "").strip() or None
    if phone and db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=400, detail="An account with this phone number already exists")
    state, district = normalize_location(officer.state, officer.district)
    new_officer = User(
        full_name=full_name,
        email=email,
        phone=phone,
        password=hash_password(password),
        role="Officer",
        department_id=current_department.department_id,
        state=state,
        district=district,
        area=(officer.area or "").strip() or None,
        specialization=(officer.specialization or "General").strip() or "General",
        max_active_cases=officer.max_active_cases,
        is_active=True,
    )
    db.add(new_officer)
    db.commit()
    db.refresh(new_officer)
    return {"message": "Officer account created", "user_id": new_officer.user_id}


@router.put("/officers/{officer_id}/profile")
def update_officer_profile(
    officer_id: int,
    profile: OfficerProfileUpdate,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    """Department Heads maintain existing officers' contact and posting data."""
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the Department Head can edit officer profiles")

    officer = db.query(User).filter(
        User.user_id == officer_id,
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer",
    ).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found in this department")

    email = profile.email.strip().lower()
    email_owner = db.query(User.user_id).filter(
        func.lower(User.email) == email,
        User.user_id != officer_id,
    ).first()
    if email_owner:
        raise HTTPException(status_code=409, detail="Another account already uses this email address")

    phone = (profile.phone or "").strip() or None
    if phone:
        phone_owner = db.query(User.user_id).filter(
            User.phone == phone,
            User.user_id != officer_id,
        ).first()
        if phone_owner:
            raise HTTPException(status_code=409, detail="Another account already uses this phone number")

    state, district = normalize_location(profile.state, profile.district)
    officer.full_name = profile.full_name.strip()
    officer.email = email
    officer.phone = phone
    officer.state = state
    officer.district = district
    officer.area = (profile.area or "").strip() or None
    officer.specialization = (profile.specialization or "General").strip() or "General"
    officer.max_active_cases = profile.max_active_cases
    db.commit()
    return {"message": f"Officer profile for {officer.full_name} updated", "user_id": officer.user_id}


@router.put("/complaint/{complaint_id}/assign-officer/{officer_id}")
def assign_complaint_to_officer(
    complaint_id: int,
    officer_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can assign complaints")
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.department_id == current_department.department_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    officer = db.query(User).filter(
        User.user_id == officer_id,
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer",
        User.is_active != False
    ).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found in this department")

    assignment = _assignment_for(complaint_id, db)
    previous_officer_id = assignment.officer_id if assignment else None
    if assignment:
        assignment.officer_id = officer.user_id
        assignment.assigned_by = _actor_name(current_department)
        assignment.updated_at = datetime.now(timezone.utc)
    else:
        assignment = ComplaintAssignment(
            complaint_id=complaint_id,
            officer_id=officer.user_id,
            assigned_by=_actor_name(current_department)
        )
        db.add(assignment)

    if previous_officer_id and previous_officer_id != officer.user_id:
        create_notification(
            db, notification_type="complaint_reassigned", title=f"Complaint #{complaint_id} reassigned",
            message=f"Complaint #{complaint_id} has been reassigned to another officer. It is no longer in your active queue.",
            complaint_id=complaint_id, recipient_user_id=previous_officer_id,
        )
    create_notification(
        db, notification_type="complaint_assigned" if previous_officer_id is None else "complaint_reassigned",
        title=f"Complaint #{complaint_id} assigned to you",
        message=f"{display_operational_title(complaint.translated_title or complaint.title, complaint.predicted_department, complaint.translated_text or complaint.description)} has been assigned to you by {_actor_name(current_department)}.",
        complaint_id=complaint_id, recipient_user_id=officer.user_id,
    )

    db.add(ComplaintEvent(
        complaint_id=complaint_id,
        event_type="officer_assignment",
        title=f"Assigned to {officer.full_name}",
        detail=f"Individual accountability assigned within {current_department.department_name}.",
        actor=_actor_name(current_department)
    ))
    db.commit()
    return {"message": f"Complaint assigned to {officer.full_name}"}


def _officer_assignment_score(officer, complaint, db, historical_metrics=None):
    """Rank eligible officers using transparent, explainable operational signals."""
    assignments = db.query(ComplaintAssignment).filter(ComplaintAssignment.officer_id == officer.user_id).all()
    ids = [a.complaint_id for a in assignments]
    assigned_complaints = db.query(Complaint).filter(Complaint.complaint_id.in_(ids)).all() if ids else []
    unresolved = [c for c in assigned_complaints if c.status != "Resolved"]
    breaches = sum(1 for c in unresolved if _sla_info(c, db)["state"] == "Breached")

    score = 0.0
    reasons = []
    # District matches are meaningful only inside the same state. A district
    # with the same spelling elsewhere must never receive the local-fit bonus.
    officer_state, officer_district = normalize_location(officer.state, officer.district)
    complaint_state, complaint_district = normalize_location(complaint.state, complaint.district)
    officer_state = (officer_state or "").strip().casefold()
    complaint_state = (complaint_state or "").strip().casefold()
    same_state = bool(officer_state and complaint_state and officer_state == complaint_state)
    same_district = bool(
        same_state and officer.district and complaint.district
        and (officer_district or "").strip().casefold() == (complaint_district or "").strip().casefold()
    )
    if same_district:
        score += 35
        reasons.append("same district and state")
    elif same_state:
        score += 18
        reasons.append("same state")
    else:
        score -= 40
        reasons.append("outside complaint state")
    if same_district and officer.area and complaint.area and officer.area.strip().casefold() == complaint.area.strip().casefold():
        score += 12
        reasons.append("same posted locality")

    # Specialization is entered by the department head (e.g. roads, transformer, drainage).
    specialization = (officer.specialization or "").lower().strip()
    if specialization and specialization != "general":
        complaint_text = f"{complaint.title or ''} {complaint.description or ''} {complaint.predicted_department or ''}".lower()
        tokens = [t.strip() for t in specialization.replace(';', ',').split(',') if t.strip()]
        matches = [t for t in tokens if t in complaint_text]
        if matches:
            score += min(25, 12 + 5 * len(matches))
            reasons.append("specialization match")

    capacity = max(1, officer.max_active_cases or 20)
    active = len(unresolved)
    load_ratio = active / capacity
    if active == 0:
        score += 25
        reasons.append("no active workload")
    elif load_ratio < 0.5:
        score += 20
        reasons.append("low workload")
    elif load_ratio < 0.8:
        score += 12
        reasons.append("available capacity")
    elif load_ratio <= 1.0:
        score += 4
        reasons.append("near capacity")
    else:
        score -= 25
        reasons.append("over capacity")

    if breaches == 0:
        score += 10
        reasons.append("no current SLA breach")
    else:
        score -= min(20, breaches * 5)
        reasons.append(f"{breaches} active SLA breach(es)")

    resolved = sum(1 for c in assigned_complaints if c.status == "Resolved")
    if resolved >= 5 and len(assigned_complaints) > 0:
        resolution_ratio = resolved / len(assigned_complaints)
        score += min(5, round(resolution_ratio * 5, 1))

    metrics = (historical_metrics or {}).get(officer.user_id)
    performance_index = metrics.get("performance_index") if metrics else None
    if performance_index is not None:
        score += round(max(0, min(100, performance_index)) * 0.15, 1)
        reasons.append(f"historical performance index {performance_index}/100")
    elif metrics and not metrics.get("assigned_historical"):
        reasons.append("no historical points yet")

    return {
        "user_id": officer.user_id,
        "name": officer.full_name,
        "email": officer.email,
        "district": officer.district,
        "state": officer.state,
        "area": officer.area,
        "specialization": officer.specialization or "General",
        "active_cases": active,
        "max_active_cases": capacity,
        "sla_breaches": breaches,
        "performance_index": performance_index,
        "assigned_historical": metrics.get("assigned_historical", 0) if metrics else 0,
        "fit_score": round(max(0.0, min(100.0, score)), 1),
        "reasons": reasons,
    }


def _rank_geographically_eligible_officers(officers, complaint, db):
    """Prefer exact-district staff, then same-state staff. Never recommend
    someone from another state as an operational assignment."""
    state, district = normalize_location(complaint.state, complaint.district)
    state = (state or "").strip().casefold()
    district = (district or "").strip().casefold()
    same_state = [
        o for o in officers
        if state and (normalize_location(o.state, o.district)[0] or "").strip().casefold() == state
    ]
    same_district = [
        o for o in same_state
        if district and (normalize_location(o.state, o.district)[1] or "").strip().casefold() == district
    ]
    candidates = same_district or same_state
    metrics = officer_metrics_for_ids(db, [officer.user_id for officer in candidates])
    ranked = [_officer_assignment_score(o, complaint, db, metrics) for o in candidates]
    ranked.sort(key=lambda row: (-row["fit_score"], row["active_cases"], row["name"]))
    scope = "same_district" if same_district else "same_state" if same_state else "no_same_state_officer"
    return ranked, scope


@router.get("/complaint/{complaint_id}/officer-recommendations")
def officer_recommendations(
    complaint_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can view assignment recommendations")
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.department_id == current_department.department_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    officers = db.query(User).filter(
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer",
        User.is_active != False
    ).all()
    ranked, geographic_scope = _rank_geographically_eligible_officers(officers, complaint, db)
    return {
        "complaint_id": complaint_id,
        "recommended": ranked[0] if ranked else None,
        "candidates": ranked[:5],
        "method": "district/state first, then posted locality + specialization + capacity + SLA history + historical performance index",
        "geographic_scope": geographic_scope,
    }


@router.post("/complaint/{complaint_id}/assign-recommended")
def assign_recommended_officer(
    complaint_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can assign complaints")
    complaint = db.query(Complaint).filter(
        Complaint.complaint_id == complaint_id,
        Complaint.department_id == current_department.department_id
    ).first()
    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")
    officers = db.query(User).filter(
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer",
        User.is_active != False
    ).all()
    ranked, _geographic_scope = _rank_geographically_eligible_officers(officers, complaint, db)
    if not ranked:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No active officer is posted in {complaint.state}. Add/reactivate an officer in this state, "
                "or use manual assignment if an approved exception is needed."
            ),
        )
    best = ranked[0]
    officer = db.query(User).filter(User.user_id == best["user_id"]).first()

    assignment = _assignment_for(complaint_id, db)
    previous_officer_id = assignment.officer_id if assignment else None
    if assignment:
        assignment.officer_id = officer.user_id
        assignment.assigned_by = _actor_name(current_department)
        assignment.updated_at = datetime.now(timezone.utc)
    else:
        assignment = ComplaintAssignment(
            complaint_id=complaint_id, officer_id=officer.user_id, assigned_by=_actor_name(current_department)
        )
        db.add(assignment)
    if previous_officer_id and previous_officer_id != officer.user_id:
        create_notification(
            db, notification_type="complaint_reassigned", title=f"Complaint #{complaint_id} reassigned",
            message=f"Complaint #{complaint_id} has been reassigned to another officer. It is no longer in your active queue.",
            complaint_id=complaint_id, recipient_user_id=previous_officer_id,
        )
    create_notification(
        db, notification_type="complaint_assigned" if previous_officer_id is None else "complaint_reassigned",
        title=f"Complaint #{complaint_id} assigned to you",
        message=f"{display_operational_title(complaint.translated_title or complaint.title, complaint.predicted_department, complaint.translated_text or complaint.description)} has been assigned to you by {_actor_name(current_department)}.",
        complaint_id=complaint_id, recipient_user_id=officer.user_id,
    )
    db.add(ComplaintEvent(
        complaint_id=complaint_id,
        event_type="smart_officer_assignment",
        title=f"Smart assignment: {officer.full_name}",
        detail="Recommended using locality, specialization, workload/capacity and SLA history. Manager accepted the recommendation.",
        actor=_actor_name(current_department)
    ))
    db.commit()
    return {"message": f"Complaint assigned to recommended officer {officer.full_name}", "officer": best}


@router.patch("/officers/{officer_id}/status")
def set_officer_status(
    officer_id: int,
    status: OfficerStatusUpdate,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db)
):
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can manage officer accounts")
    officer = db.query(User).filter(
        User.user_id == officer_id,
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer"
    ).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found")
    officer.is_active = status.is_active
    db.commit()
    return {"message": f"{officer.full_name} {'activated' if status.is_active else 'deactivated'}", "is_active": status.is_active}


@router.delete("/officers/{officer_id}")
def delete_officer(
    officer_id: int,
    current_department: Department = Depends(get_current_department),
    db: Session = Depends(get_db),
):
    """Permanently remove an officer after active cases have been reassigned.

    Historical ComplaintEvent rows are retained (they store actor names as
    snapshots). Assignment rows are removed only after no unresolved complaint
    remains assigned to this officer.
    """
    if _actor_role(current_department) == "officer":
        raise HTTPException(status_code=403, detail="Only the department manager can delete officer accounts")

    officer = db.query(User).filter(
        User.user_id == officer_id,
        User.department_id == current_department.department_id,
        func.lower(User.role) == "officer",
    ).first()
    if not officer:
        raise HTTPException(status_code=404, detail="Officer not found in this department")

    active_rows = (
        db.query(ComplaintAssignment.complaint_id)
        .join(Complaint, Complaint.complaint_id == ComplaintAssignment.complaint_id)
        .filter(
            ComplaintAssignment.officer_id == officer_id,
            or_(Complaint.status.is_(None), func.lower(Complaint.status) != "resolved"),
        )
        .all()
    )
    active_ids = [row[0] for row in active_rows]
    if active_ids:
        preview = ", ".join(f"#{cid}" for cid in active_ids[:8])
        more = f" and {len(active_ids) - 8} more" if len(active_ids) > 8 else ""
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot delete {officer.full_name}: reassign or resolve active complaint(s) "
                f"{preview}{more} first. You can deactivate the officer meanwhile."
            ),
        )

    # Keep the event/audit timeline; remove assignment FK rows so the user row
    # can be deleted without leaving a broken foreign key.
    db.query(ComplaintAssignment).filter(
        ComplaintAssignment.officer_id == officer_id
    ).delete(synchronize_session=False)
    name = officer.full_name
    db.delete(officer)
    db.commit()
    return {"message": f"Officer {name} permanently deleted. Historical complaint events remain available."}
