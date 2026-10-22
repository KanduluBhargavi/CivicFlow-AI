from datetime import datetime, timezone

from app.models.complaint import Complaint
from app.models.complaint_escalation import ComplaintEscalation
from app.services.sla_service import sla_info


def complaint_sla_state(complaint, db=None):
    return sla_info(complaint, db)["state"]


def desired_escalation(complaint, db=None):
    """Return an operational escalation level grounded in recorded case state.

    L1: SLA at risk / managerial attention.
    L2: SLA breached.
    L3: critical complaint with an SLA breach.
    """
    state = complaint_sla_state(complaint, db)

    if complaint.status == "Resolved":
        return 0, None

    if state == "Breached" and complaint.priority == "Critical":
        return 3, "Critical-priority complaint has breached its SLA and requires system-level attention."

    if state == "Breached":
        return 2, "Complaint has breached its SLA and requires department-head escalation."

    if state == "At Risk":
        return 1, "Complaint has entered the SLA at-risk window and requires managerial follow-up."

    return 0, None


def sync_automatic_escalations(db, complaints):
    """Create/upgrade automatic escalation records without duplicating them."""
    changed = False

    complaint_ids = [c.complaint_id for c in complaints]
    if not complaint_ids:
        return False

    rows = (
        db.query(ComplaintEscalation)
        .filter(
            ComplaintEscalation.complaint_id.in_(complaint_ids),
            ComplaintEscalation.status.in_(["Open", "Acknowledged"]),
        )
        .all()
    )
    active = {}
    for row in rows:
        current = active.get(row.complaint_id)
        if current is None or row.level > current.level:
            active[row.complaint_id] = row

    now = datetime.now(timezone.utc)

    for complaint in complaints:
        desired_level, reason = desired_escalation(complaint, db)
        current = active.get(complaint.complaint_id)

        if desired_level == 0:
            if current and current.source == "Automatic":
                current.status = "Closed"
                current.resolved_at = now
                changed = True
            continue

        if current:
            if current.source == "Automatic" and desired_level > current.level:
                current.level = desired_level
                current.reason = reason
                current.status = "Open"
                changed = True
            continue

        db.add(
            ComplaintEscalation(
                complaint_id=complaint.complaint_id,
                level=desired_level,
                reason=reason,
                source="Automatic",
                status="Open",
                escalated_by="CivicFlow SLA Monitor",
            )
        )
        changed = True

    if changed:
        db.commit()
    return changed
