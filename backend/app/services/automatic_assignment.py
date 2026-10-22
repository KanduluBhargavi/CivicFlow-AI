"""Periodic, auditable fallback assignment for department queues."""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.complaint import Complaint
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_delay_request import ComplaintDelayRequest
from app.models.complaint_event import ComplaintEvent
from app.models.department import Department
from app.models.user import User
from app.services.in_app_notifications import create_notification
from app.services.sla_service import ASSIGNMENT_HOURS, assignment_deadline
from app.utils.complaint_titles import display_operational_title


def auto_assign_overdue_complaints(db, now=None):
    """Assign eligible, local, under-capacity staff after the head's due time.

    The existing explainable ranking considers posting, specialization,
    workload, active breaches, completed-case outcomes and historical points.
    This worker never assigns across state boundaries or over capacity.
    """
    from app.routes.department_routes import _rank_geographically_eligible_officers

    now = now or datetime.now(timezone.utc)
    assignment_exists = db.query(ComplaintAssignment.assignment_id).filter(
        ComplaintAssignment.complaint_id == Complaint.complaint_id
    ).exists()
    pending = db.query(Complaint).filter(
        Complaint.department_id.isnot(None),
        # Only route cases still waiting in the department-head queue.
        # Never attach an officer retroactively to a case already in progress.
        Complaint.status == "Assigned",
        ~assignment_exists,
    ).all()

    assigned_count = 0
    for complaint in pending:
        start = complaint.assigned_at or complaint.created_at
        if start and start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        proposed_due = assignment_deadline(start, complaint.priority)
        if proposed_due:
            if complaint.officer_assignment_due_at is None:
                complaint.officer_assignment_due_at = proposed_due
            elif complaint.officer_assignment_due_at > proposed_due:
                # A newly elevated urgent priority may bring assignment forward,
                # but a lower priority never silently extends a waiting case.
                complaint.officer_assignment_due_at = proposed_due
        due_at = complaint.officer_assignment_due_at
        if not due_at:
            continue
        if due_at.tzinfo is None:
            due_at = due_at.replace(tzinfo=timezone.utc)
        if due_at > now:
            continue

        officers = db.query(User).filter(
            User.department_id == complaint.department_id,
            User.role.ilike("officer"),
            User.is_active.isnot(False),
        ).all()
        ranked, _scope = _rank_geographically_eligible_officers(officers, complaint, db)
        available = [row for row in ranked if row["active_cases"] < row["max_active_cases"]]
        title = display_operational_title(
            complaint.translated_title or complaint.title,
            complaint.predicted_department,
            complaint.translated_text or complaint.description,
        )
        department = db.query(Department).filter(
            Department.department_id == complaint.department_id
        ).first()

        if not available:
            if department:
                create_notification(
                    db,
                    notification_type="auto_assignment_blocked",
                    title=f"No eligible officer for complaint #{complaint.complaint_id}",
                    message=(
                        f"The assignment wait has expired for {title}, but no active officer in the complaint's state "
                        "has available capacity. Review posting, specialization and officer capacity."
                    ),
                    complaint_id=complaint.complaint_id,
                    recipient_department_id=department.department_id,
                    dedupe_key=f"auto-assignment-blocked:{complaint.complaint_id}",
                )
                db.commit()
            continue

        best = available[0]
        previous = db.query(ComplaintAssignment).filter(
            ComplaintAssignment.complaint_id == complaint.complaint_id
        ).first()
        if previous:
            continue
        assignment = ComplaintAssignment(
            complaint_id=complaint.complaint_id,
            officer_id=best["user_id"],
            assigned_by="CivicFlow Auto-Assignment",
            assigned_at=now,
            updated_at=now,
        )
        db.add(assignment)
        try:
            db.flush()
            db.add(ComplaintEvent(
                complaint_id=complaint.complaint_id,
                event_type="automatic_officer_assignment",
                title=f"Automatically assigned to {best['name']}",
                detail=(
                    f"The Department Head assignment window ({ASSIGNMENT_HOURS.get(complaint.priority, 8)}h for "
                    f"{complaint.priority or 'Medium'} priority) elapsed. Ranked by posted locality, specialization, "
                    f"available capacity, SLA history and historical performance. Suitability score {best['fit_score']}/100 (routing estimate, not a skill guarantee); "
                    f"officer had {best['active_cases']}/{best['max_active_cases']} active cases."
                ),
                actor="CivicFlow Auto-Assignment",
            ))
            create_notification(
                db,
                notification_type="complaint_auto_assigned",
                title=f"Complaint #{complaint.complaint_id} assigned to you",
                message=f"{title} was assigned to you automatically after the Department Head assignment window expired.",
                complaint_id=complaint.complaint_id,
                recipient_user_id=best["user_id"],
                dedupe_key=f"complaint-auto-assigned:officer:{complaint.complaint_id}",
            )
            if department:
                create_notification(
                    db,
                    notification_type="complaint_auto_assigned",
                    title=f"Complaint #{complaint.complaint_id} auto-assigned",
                    message=f"{title} was assigned to {best['name']} after the assignment window expired.",
                    complaint_id=complaint.complaint_id,
                    recipient_department_id=department.department_id,
                    dedupe_key=f"complaint-auto-assigned:department:{complaint.complaint_id}",
                )
            if complaint.citizen_id:
                create_notification(
                    db,
                    notification_type="officer_assignment",
                    title="An officer has been assigned to your complaint",
                    message=f"{title} is now assigned to an officer for follow-up.",
                    complaint_id=complaint.complaint_id,
                    recipient_user_id=complaint.citizen_id,
                    dedupe_key=f"complaint-auto-assigned:citizen:{complaint.complaint_id}",
                )
            db.commit()
            assigned_count += 1
        except IntegrityError:
            db.rollback()  # Another worker/manual action won the unique assignment race.
        except Exception:
            db.rollback()
            raise
    return assigned_count


def run_assignment_cycle():
    db = SessionLocal()
    try:
        return auto_assign_overdue_complaints(db)
    finally:
        db.close()


def notify_due_delay_followups(db, now=None):
    """Notify the officer and Head once an approved quiet period ends."""
    now = now or datetime.now(timezone.utc)
    due = db.query(ComplaintDelayRequest).filter(
        ComplaintDelayRequest.status == "Approved",
        ComplaintDelayRequest.requested_until <= now,
        ComplaintDelayRequest.followup_sent.is_(False),
    ).all()
    sent = 0
    for request in due:
        complaint = db.query(Complaint).filter(
            Complaint.complaint_id == request.complaint_id
        ).first()
        if not complaint:
            request.followup_sent = True
            continue
        text = f"The approved follow-up time has arrived for complaint #{complaint.complaint_id}. Record the current work status or submit a new delay request."
        create_notification(
            db, notification_type="officer_delay_followup",
            title="Approved follow-up time reached",
            message=text,
            complaint_id=complaint.complaint_id,
            recipient_user_id=request.officer_id,
            dedupe_key=f"officer-delay-followup:{request.request_id}:officer",
        )
        if complaint.department_id:
            create_notification(
                db, notification_type="officer_delay_followup",
                title=f"Follow-up due for complaint #{complaint.complaint_id}",
                message=text,
                complaint_id=complaint.complaint_id,
                recipient_department_id=complaint.department_id,
                dedupe_key=f"officer-delay-followup:{request.request_id}:head",
            )
        db.add(ComplaintEvent(
            complaint_id=complaint.complaint_id,
            event_type="delay_followup_due",
            title="Approved follow-up time reached",
            detail="CivicFlow sent a single reminder to the assigned officer and Department Head. The original SLA remains auditable.",
            actor="CivicFlow",
        ))
        request.followup_sent = True
        sent += 1
    if due:
        db.commit()
    return sent


def run_delay_followup_cycle():
    db = SessionLocal()
    try:
        return notify_due_delay_followups(db)
    finally:
        db.close()
