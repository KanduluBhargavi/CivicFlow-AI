from collections import defaultdict

from sqlalchemy import func

from app.models.complaint import Complaint
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_event import ComplaintEvent
from app.models.contact import Feedback
from app.services.sla_service import sla_info


def _aware(value):
    if value is None:
        return None
    if value.tzinfo is None:
        from datetime import timezone
        return value.replace(tzinfo=timezone.utc)
    return value


def officer_metrics_for_ids(db, officer_ids):
    """Return transparent historical metrics using actual stored assignments.

    No synthetic score inputs are used. Metrics are computed from complaint
    assignment/status timestamps, complaint events and citizen ratings.
    """
    officer_ids = list(officer_ids or [])
    if not officer_ids:
        return {}

    assignments = (
        db.query(ComplaintAssignment)
        .filter(ComplaintAssignment.officer_id.in_(officer_ids))
        .all()
    )
    complaint_ids = [a.complaint_id for a in assignments]
    assignment_by_complaint = {a.complaint_id: a.officer_id for a in assignments}

    complaints = (
        db.query(Complaint)
        .filter(Complaint.complaint_id.in_(complaint_ids))
        .all()
        if complaint_ids else []
    )

    events = (
        db.query(ComplaintEvent)
        .filter(
            ComplaintEvent.complaint_id.in_(complaint_ids),
            ComplaintEvent.event_type == "citizen_reopen",
        )
        .all()
        if complaint_ids else []
    )

    feedback_rows = (
        db.query(Feedback.complaint_id, func.avg(Feedback.rating), func.count(Feedback.feedback_id))
        .filter(Feedback.complaint_id.in_(complaint_ids))
        .group_by(Feedback.complaint_id)
        .all()
        if complaint_ids else []
    )
    feedback_by_complaint = {
        complaint_id: {"avg": float(avg_rating), "count": int(count)}
        for complaint_id, avg_rating, count in feedback_rows
        if complaint_id is not None
    }

    reopened_counts = defaultdict(int)
    for event in events:
        reopened_counts[event.complaint_id] += 1

    complaints_by_officer = defaultdict(list)
    for complaint in complaints:
        officer_id = assignment_by_complaint.get(complaint.complaint_id)
        if officer_id:
            complaints_by_officer[officer_id].append(complaint)

    result = {}
    for officer_id in officer_ids:
        rows = complaints_by_officer.get(officer_id, [])
        resolved = [c for c in rows if c.status == "Resolved" and c.resolved_at]
        unresolved = [c for c in rows if c.status != "Resolved"]

        resolution_hours = []
        sla_met = 0
        sla_evaluated = 0
        for c in resolved:
            start = _aware(c.assigned_at or c.created_at)
            end = _aware(c.resolved_at)
            if start and end:
                hours = max(0.0, (end - start).total_seconds() / 3600)
                resolution_hours.append(hours)
                target_hours = sla_info(c, db)["target_hours"]
                if target_hours is not None:
                    sla_evaluated += 1
                if target_hours is not None and hours <= target_hours:
                    sla_met += 1

        ratings = []
        rating_count = 0
        for c in rows:
            f = feedback_by_complaint.get(c.complaint_id)
            if f:
                ratings.append(f["avg"])
                rating_count += f["count"]

        total = len(rows)
        resolved_count = len(resolved)
        resolution_rate = (resolved_count / total * 100) if total else 0.0
        sla_compliance = (sla_met / sla_evaluated * 100) if sla_evaluated else None
        avg_resolution = (
            sum(resolution_hours) / len(resolution_hours)
            if resolution_hours else None
        )
        avg_rating = (sum(ratings) / len(ratings)) if ratings else None
        reopened = sum(reopened_counts[c.complaint_id] for c in rows)

        # Transparent operational index; only shown when there is historical data.
        index_parts = []
        if total:
            index_parts.append(resolution_rate)
        if sla_compliance is not None:
            index_parts.append(sla_compliance)
        if avg_rating is not None:
            index_parts.append(avg_rating / 5 * 100)
        performance_index = (
            round(sum(index_parts) / len(index_parts), 1)
            if index_parts else None
        )

        result[officer_id] = {
            "assigned_historical": total,
            "active_cases": len(unresolved),
            "resolved_historical": resolved_count,
            "resolution_rate": round(resolution_rate, 1),
            "avg_resolution_hours": round(avg_resolution, 1) if avg_resolution is not None else None,
            "sla_compliance_rate": round(sla_compliance, 1) if sla_compliance is not None else None,
            "reopened_cases": int(reopened),
            "avg_citizen_rating": round(avg_rating, 2) if avg_rating is not None else None,
            "rating_count": rating_count,
            "performance_index": performance_index,
        }

    return result
