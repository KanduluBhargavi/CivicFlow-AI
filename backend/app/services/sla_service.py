"""Transparent repair-time targets based on comparable completed complaints.

Targets use past resolution durations for the same department, priority and
complaint text where possible. Sparse local history falls back to broader
department or cross-department history; estimates become more specific as the
system collects resolved cases.
"""
from __future__ import annotations

import re
import statistics
from datetime import datetime, timezone, timedelta

from app.models.complaint import Complaint

PRIORITIES = {"Critical", "High", "Medium", "Low"}
MIN_COMPARABLE_CASES = 3
_STOP_WORDS = {
    "about", "after", "again", "also", "been", "being", "from", "have", "into",
    "near", "over", "same", "that", "their", "there", "these", "they", "this",
    "through", "under", "very", "were", "when", "where", "which", "with", "would",
    "complaint", "please", "issue", "problem", "area", "street", "people", "need",
}


def _aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _text(complaint):
    return " ".join(str(value or "") for value in (
        complaint.translated_title, complaint.translated_text, complaint.ai_summary,
        complaint.title, complaint.description,
    )).lower()


def _tokens(complaint):
    return {word for word in re.findall(r"[a-z0-9]{3,}", _text(complaint)) if word not in _STOP_WORDS}


def _text_similarity(left, right):
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _percentile(values, fraction):
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def estimate_resolution_target(db, complaint):
    """Estimate from progressively broader completed-work history.

    The first choice is similar text in this department and priority. If the
    department has too few examples, widen to this department/priority, then
    similar text across departments, then the same priority across departments.
    This avoids inventing a repair duration while still returning a useful
    estimate for new departments with sparse history.
    """
    priority = complaint.priority if complaint.priority in PRIORITIES else "Medium"
    key = (complaint.department_id, priority)
    history_cache = db.info.setdefault("_resolution_history_cache", {})
    if key not in history_cache:
        query = db.query(Complaint).filter(
            Complaint.status == "Resolved",
            Complaint.resolved_at.isnot(None),
            Complaint.priority == priority,
            Complaint.complaint_id != complaint.complaint_id,
        )
        if complaint.department_id:
            query = query.filter(Complaint.department_id == complaint.department_id)
        history_cache[key] = query.order_by(Complaint.resolved_at.desc()).limit(1000).all()
    history = history_cache[key]

    samples = []
    for past in history:
        start, end = _aware(past.assigned_at or past.created_at), _aware(past.resolved_at)
        if not start or not end or end < start:
            continue
        hours = (end - start).total_seconds() / 3600
        if hours < 0 or hours > 24 * 365:
            continue
        samples.append((past, hours))

    similar = [(past, hours) for past, hours in samples if _text_similarity(complaint, past) >= 0.10]
    selected, basis = [], ""
    if len(similar) >= MIN_COMPARABLE_CASES:
        selected, basis = similar, "similar_department_priority_text"
    elif len(samples) >= MIN_COMPARABLE_CASES:
        selected, basis = samples, "department_priority_history"
    else:
        global_cache = db.info.setdefault("_global_resolution_history_cache", {})
        if priority not in global_cache:
            global_cache[priority] = db.query(Complaint).filter(
                Complaint.status == "Resolved",
                Complaint.resolved_at.isnot(None),
                Complaint.priority == priority,
                Complaint.department_id != complaint.department_id,
                Complaint.complaint_id != complaint.complaint_id,
            ).order_by(Complaint.resolved_at.desc()).limit(2000).all()
        global_samples = []
        for past in global_cache[priority]:
            start, end = _aware(past.assigned_at or past.created_at), _aware(past.resolved_at)
            if not start or not end or end < start:
                continue
            hours = (end - start).total_seconds() / 3600
            if 0 <= hours <= 24 * 365:
                global_samples.append((past, hours))
        global_similar = [item for item in global_samples if _text_similarity(complaint, item[0]) >= 0.10]
        if len(global_similar) >= MIN_COMPARABLE_CASES:
            selected, basis = global_similar, "similar_cross_department_priority_history"
        elif len(global_samples) >= MIN_COMPARABLE_CASES:
            selected, basis = global_samples, "cross_department_priority_history"
        else:
            selected = similar or samples or global_similar or global_samples
            basis = "limited_historical_estimate" if selected else "initial_text_priority_estimate"

    if selected:
        durations = [hours for _, hours in selected]
        sample_size = len(durations)
        median = max(1.0, statistics.median(durations))
        return {
            "target_hours": round(median, 1),
            "lower_hours": round(max(0.0, _percentile(durations, 0.25)), 1),
            "upper_hours": round(_percentile(durations, 0.75), 1),
            "sample_size": sample_size, "basis": basis, "priority": priority,
        }

    # Cold-start estimate: classify the kind of work from the English
    # processing text and return a visible range. It is explicitly labelled as
    # an initial planning estimate; subsequent cases replace it with observed
    # resolution history. Priority influences response coordination, while
    # complexity cues prevent a critical infrastructure repair being treated
    # like a simple inspection.
    text = _text(complaint)
    if re.search(r"(excavat|replace|rebuild|collapse|major pipeline|trunk main|bridge|road surface|structural)", text):
        base = 120.0
    elif re.search(r"(contaminat|sewage|burst|widespread|multiple ward|major leak|outage|flood|unsafe water)", text):
        base = 72.0
    elif re.search(r"(leak|blocked|clog|broken|damaged|not working|no water|overflow|repair)", text):
        base = 36.0
    elif re.search(r"(inspection|check|assessment|missed collection|streetlight|single)", text):
        base = 16.0
    else:
        base = 48.0
    priority_factor = {"Critical": 0.85, "High": 0.95, "Medium": 1.0, "Low": 1.1}.get(priority, 1.0)
    estimate = max(4.0, base * priority_factor)
    return {
        "target_hours": round(estimate, 1),
        "lower_hours": round(estimate * 0.6, 1),
        "upper_hours": round(estimate * 1.8, 1),
        "sample_size": 0, "basis": basis, "priority": priority,
    }


def set_resolution_target(db, complaint, *, tighten_only=False):
    """Persist a snapshot so the target does not drift as new cases close."""
    estimate = estimate_resolution_target(db, complaint)
    old_hours = complaint.sla_target_hours
    if tighten_only and old_hours is not None and estimate["target_hours"] is not None:
        estimate["target_hours"] = min(float(old_hours), estimate["target_hours"])
    complaint.sla_target_hours = estimate["target_hours"]
    complaint.sla_target_lower_hours = estimate["lower_hours"]
    complaint.sla_target_upper_hours = estimate["upper_hours"]
    complaint.sla_target_sample_size = estimate["sample_size"]
    complaint.sla_target_basis = estimate["basis"]
    complaint.sla_target_priority = estimate["priority"]
    db.info.setdefault("_sla_target_cache", {})[(complaint.complaint_id, estimate["priority"])] = dict(estimate)
    return estimate


def sla_info(complaint, db=None):
    priority = complaint.priority if complaint.priority in PRIORITIES else "Medium"
    if db is not None and (complaint.sla_target_hours is None or complaint.sla_target_priority != priority):
        cache = db.info.setdefault("_sla_target_cache", {})
        cached = cache.get((complaint.complaint_id, priority))
        if cached is not None and complaint.sla_target_hours is None:
            complaint.sla_target_hours = cached["target_hours"]
            complaint.sla_target_lower_hours = cached["lower_hours"]
            complaint.sla_target_upper_hours = cached["upper_hours"]
            complaint.sla_target_sample_size = cached["sample_size"]
            complaint.sla_target_basis = cached["basis"]
            complaint.sla_target_priority = cached["priority"]
        else:
            set_resolution_target(db, complaint, tighten_only=complaint.sla_target_hours is not None)
    hours = float(complaint.sla_target_hours) if complaint.sla_target_hours is not None else None
    start = _aware(complaint.assigned_at or complaint.created_at)
    if not start or hours is None:
        return {
            "target_hours": hours, "deadline": None,
            "state": "Not Estimated" if complaint.status == "Resolved" else "Needs Assessment",
            "remaining_minutes": None, "progress_percent": 0,
            "basis": complaint.sla_target_basis or "insufficient_comparable_history",
            "sample_size": complaint.sla_target_sample_size or 0,
            "lower_hours": complaint.sla_target_lower_hours,
            "upper_hours": complaint.sla_target_upper_hours,
        }
    deadline = start + timedelta(hours=hours)
    now = datetime.now(timezone.utc)
    # An approved officer delay suppresses breach reminders only until the
    # Head-approved follow-up time. The original estimate is retained in the
    # audit history and resumes as overdue if that follow-up is missed.
    if db is not None and complaint.status != "Resolved":
        from app.models.complaint_delay_request import ComplaintDelayRequest
        approved_delay = db.query(ComplaintDelayRequest).filter(
            ComplaintDelayRequest.complaint_id == complaint.complaint_id,
            ComplaintDelayRequest.status == "Approved",
            ComplaintDelayRequest.requested_until > now,
        ).order_by(ComplaintDelayRequest.requested_until.desc()).first()
        if approved_delay:
            approved_until = _aware(approved_delay.requested_until)
            return {
                "target_hours": round(hours, 1), "deadline": approved_until,
                "state": "Approved Extension",
                "remaining_minutes": int((approved_until - now).total_seconds() // 60),
                "progress_percent": 100 if now >= start + timedelta(hours=hours) else
                    min(99, round(max(0, (now - start).total_seconds()) / (hours * 3600) * 100)),
                "basis": complaint.sla_target_basis or "insufficient_comparable_history",
                "sample_size": complaint.sla_target_sample_size or 0,
                "lower_hours": complaint.sla_target_lower_hours,
                "upper_hours": complaint.sla_target_upper_hours,
                "extension_until": approved_until,
            }
    remaining = int((deadline - now).total_seconds() // 60)
    progress = min(100, round(max(0, (now - start).total_seconds()) / (hours * 3600) * 100))
    if complaint.status == "Resolved":
        resolved_at = _aware(complaint.resolved_at)
        state = "Met" if resolved_at and resolved_at <= deadline else "Breached"
    elif remaining < 0:
        state = "Breached"
    elif progress >= 80:
        state = "At Risk"
    else:
        state = "On Track"
    return {
        "target_hours": round(hours, 1), "deadline": deadline, "state": state,
        "remaining_minutes": remaining, "progress_percent": progress,
        "basis": complaint.sla_target_basis or "insufficient_comparable_history",
        "sample_size": complaint.sla_target_sample_size or 0,
        "lower_hours": complaint.sla_target_lower_hours,
        "upper_hours": complaint.sla_target_upper_hours,
    }


ASSIGNMENT_HOURS = {"Critical": 0.5, "High": 2, "Medium": 8, "Low": 24}


def assignment_deadline(start, priority):
    start = _aware(start)
    if not start:
        return None
    return start + timedelta(hours=ASSIGNMENT_HOURS.get(priority, 8))
