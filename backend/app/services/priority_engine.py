"""Dynamic complaint priority.

The ML text classifier (``ai_service.predict_priority_details``) only sees the
words of a complaint at submission time. Real urgency also depends on what
happens afterwards, so this module turns the ML result into a *live* score:

    final score = ML base score  +  situational boosts  (capped)

Situational factors, all recorded per complaint so officers can see *why* a
priority changed:

* people affected ("I'm affected" supporters + distinct reporters), linked
  reports, geographic spread
* essential services, public health, vulnerable people, major infrastructure
  failure, immediate-danger wording, verified emergency alert
* time open vs. the SLA, time since last update / still unresolved
* worsening, recurring, missed deadlines, failed or temporary repairs,
  citizen re-opens (text signals are detected *semantically* with Sentence-BERT,
  see semantic_signals.py; keyword patterns are only the offline fallback)
* active officer work (small relief)

Safeguards: priority never drops below the ML base class, ``Critical`` is only
given for explicit emergencies (ML safety override, verified alert, or
immediate-danger wording with a very high score) and resolved complaints are
frozen.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone

# Diagnostic marker: confirms which priority-engine implementation Python imported.
PRIORITY_ENGINE_FIX_VERSION = "2026-10-17-r4"

from app.services.sla_service import sla_info
ANCHORS = {"Low": 22.0, "Medium": 48.0, "High": 72.0}
CRITICAL_ANCHOR = 92.0
LOW_MAX, MEDIUM_MAX, HIGH_MAX = 35.0, 62.0, 88.0     # score bands
MAX_BOOST = 45.0
ORDER = ["Low", "Medium", "High", "Critical"]

ESSENTIAL_DEPARTMENTS = {"Water Supply", "Electricity", "Healthcare", "Education"}

_SIGNALS = {
    "worsening": r"getting worse|gets worse|worsen|deteriorat|spreading|expanding|growing|increasing|bigger|wider|deeper|more and more|every day (?:it|the)|rapidly|escalat",
    "recurring": r"again|recurr|repeated|keeps? (?:happening|breaking|coming)|every (?:day|night|week|month|evening|morning)|daily|regularly|frequent|once more|same problem",
    "missed_deadline": r"promised|assured|assurance|deadline|was told|were told|said they would|supposed to|no one came|nobody came|never came|did not come|didn't come|not (?:yet )?(?:fixed|done|completed|started) (?:even )?(?:after|despite)|still pending|overdue",
    "failed_repair": r"temporary (?:fix|repair|patch|solution)|patched|patch ?work|repaired (?:but|and)|fixed (?:but|and)|broke again|damaged again|failed again|repair(?:s)? (?:failed|did not|didn't)|(?:fix|repair) (?:did not|didn't) (?:work|last)|reopened",
    "essential": r"hospital|clinic|dialysis|oxygen|ambulance|school|college|anganwadi|water supply|drinking water|electricity|power supply|transformer|ration|medicine|pharmacy|health cent",
    "critical_time": r"exam|examination|night|midnight|heat ?wave|summer|monsoon|rain|storm|winter|festival|election|during the day|peak",
    "public_health": r"contaminat|sewage|sewer|drain overflow|overflowing|dirty water|polluted|unsafe water|disease|dengue|malaria|cholera|typhoid|outbreak|infection|stench|foul smell|rats|mosquito|garbage pile|open defecation|biomedical",
    "infrastructure": r"collaps|caved|cave[- ]?in|sinkhole|bridge (?:crack|damage|broke)|structural|wall (?:fell|crack)|building (?:crack|tilt)|pole (?:fell|tilt|broke)|transformer (?:burst|blast|fire)|pipeline (?:burst|broke)|water main|major (?:damage|crack|leak)|road (?:washed|breach)|embankment",
    "vulnerable": r"child|children|kid|infant|baby|student|elderly|senior citizen|old age|disab|wheelchair|blind|pregnan|patient|bedridden|orphan",
    "danger": r"immediate(?:ly)?|danger|dangerous|life[- ]threatening|emergency|urgent|accident|fatal|live wire|electrocut|spark|fire|explos|gas leak|trapped|drown|collapse|open manhole|unconscious|injur",
    "wide_scale": r"entire|whole|all (?:the )?(?:residents|houses|families|areas?|streets?|colony|locality|village|ward)|hundreds|thousands|every(?:one| house| family)|many (?:families|houses|residents|people)|several (?:streets|families|houses|colonies)|village|ward|neighbou?rhood|colony",
}
_RX = {k: re.compile(v, re.I) for k, v in _SIGNALS.items()}


def _hit(key: str, text: str) -> bool:
    return bool(_RX[key].search(text))


def text_signals(text: str, semantic: bool = True) -> dict:
    """Strength (0..1) of each situational signal in the English complaint text.

    Primary: stronger Sentence-BERT similarity to prototype sentences (understands
    paraphrases), gated by SEMANTIC_SIGNAL_MIN_STRENGTH (default 0.60) to reduce
    weak false-positive signals. Exact keyword matches remain active. Fallback
    when the model is unavailable: keyword patterns (0/1).
    """
    low = str(text or "")
    if semantic:
        try:
            from app.services.semantic_signals import signal_strengths
            strengths = signal_strengths(low)
        except Exception:
            strengths = None
        if strengths is not None:
            # Sentence embeddings can assign moderate similarity to unrelated
            # signals. Treat only stronger semantic matches as active; exact
            # lexical matches remain authoritative. This prevents several weak
            # similarities from accumulating into an unjustified escalation.
            # Values are already rescaled to [0, 1] by semantic_signals.py.
            semantic_min_strength = float(__import__("os").getenv(
                "SEMANTIC_SIGNAL_MIN_STRENGTH", "0.60"
            ))
            result = {
                k: max(
                    float(strengths.get(k, 0.0))
                    if float(strengths.get(k, 0.0)) >= semantic_min_strength else 0.0,
                    1.0 if _hit(k, low) else 0.0
                )
                for k in _SIGNALS
            }
            # Public-health risk requires evidence of a health hazard, not just
            # a routine garbage-collection complaint. SBERT can confuse generic
            # sanitation wording with a prototype about disease-spreading waste.
            # Keep semantic detection for paraphrases, but require contextual
            # evidence such as contamination, sewage, illness, pests, or a
            # stated health hazard before adding public-health points.
            health_context = re.search(
                r"contaminat|sewage|sewer|drinking water|dirty water|pollut|unsafe water|"
                r"disease|dengue|malaria|cholera|typhoid|outbreak|infection|stench|"
                r"foul smell|rats?|mosquito|rotting|health hazard|sick|ill|"
                r"diarrh|waterborne|biomedical|open defecation|toxic|mix(?:ing|ed) with water",
                low, re.I,
            )
            if not health_context:
                result["public_health"] = 0.0
            return result
    return {k: (1.0 if _hit(k, low) else 0.0) for k in _SIGNALS}


def _aware(value):
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def band(score: float) -> str:
    if score < LOW_MAX:
        return "Low"
    if score < MEDIUM_MAX:
        return "Medium"
    if score < HIGH_MAX:
        return "High"
    return "Critical"


def base_score(base_priority: str, probs: dict | None, critical: bool) -> float:
    if critical:
        return CRITICAL_ANCHOR
    if probs:
        total = sum(probs.get(k, 0.0) for k in ANCHORS)
        if total > 0:
            return sum(probs.get(k, 0.0) * ANCHORS[k] for k in ANCHORS) / total
    return ANCHORS.get(base_priority, ANCHORS["Medium"])


def compute_dynamic_priority(ctx: dict) -> dict:
    """Pure scoring function.

    ctx keys: base_priority, base_probs, critical, high_floor, text, department,
    affected_count, report_count, area_count, age_hours, since_update_hours,
    status, reopen_count, emergency_alert, actively_worked.
    """
    base = ctx.get("base_priority") or "Medium"
    if base not in ORDER:
        base = "Medium"
    critical = bool(ctx.get("critical")) or base == "Critical"
    emergency = bool(ctx.get("emergency_alert"))
    sig = ctx.get("signals") or text_signals(ctx.get("text", ""))
    factors = []

    def add(name, points, detail):
        if points:
            if abs(points) >= 0.5:        # ignore negligible partial matches
                factors.append({"factor": name, "points": round(float(points), 1), "detail": detail})

    # --- people affected & spread ---------------------------------------
    affected = max(int(ctx.get("affected_count") or 1), 1)
    people = min(12.0, 4.0 * math.log2(affected)) if affected > 1 else 0.0
    if sig["wide_scale"] >= 0.3 and affected < 4:
        people = max(people, 4.0 * sig["wide_scale"])            # citizen describes a whole neighbourhood
    add("People affected", people, f"{affected} distinct citizen(s) filed a complaint")
    supporters = max(int(ctx.get("support_count") or 0), 0)
    if supporters:
        # Support is a useful signal, but it is weaker than independently filed
        # complaints or verified affected-person counts. Cap it so clicks alone
        # cannot push an ordinary complaint across a priority band.
        support_points = min(8.5, 3.0 * math.log2(supporters + 1))
        add("Community support", support_points, f"{supporters} additional citizen(s) supported this incident")
    reports = int(ctx.get("report_count") or 1)
    if reports >= 3:
        add("Linked incident reports", min(5.0, 1.5 * math.log2(reports)), f"{reports} complaints currently linked to this incident cluster; this is not the direct semantic-match count")
    areas = int(ctx.get("area_count") or 1)
    if areas >= 2:
        add("Geographic scope", 3.0 if areas < 4 else 5.0, f"complaints from {areas} different localities")

    # --- what is affected -------------------------------------------------
    essential = 0.0
    if ctx.get("department") in ESSENTIAL_DEPARTMENTS:
        essential += 4.0
    essential += 3.0 * sig["essential"]
    if essential:
        essential += 3.0 * sig["critical_time"]
    add("Essential service", min(essential, 8.0), "essential service affected" + (" at a critical time" if sig["critical_time"] >= 0.5 and essential > 7 else ""))
    add("Public health", 6.0 * sig["public_health"], "contamination / sewage / disease risk")
    add("Major infrastructure failure", 6.0 * sig["infrastructure"], "structural or major infrastructure damage")
    add("Vulnerable people", 4.0 * sig["vulnerable"], "children, elderly, patients or disabled people involved")
    if not critical:
        add("Immediate danger", 6.0 * sig["danger"], "emergency / danger described")

    # --- trend & history --------------------------------------------------
    add("Worsening", 5.0 * sig["worsening"], "citizen reports the problem is getting worse")
    reopens = int(ctx.get("reopen_count") or 0)
    add("Recurring issue", 3.0 if reopens else 3.0 * sig["recurring"], "problem keeps recurring")
    add("Missed deadline", 4.0 * sig["missed_deadline"], "previous promise/deadline not met")
    add("Failed repair", 4.0 if reopens else 4.0 * sig["failed_repair"], "earlier or temporary repair did not hold")
    if reopens:
        add("Citizen reopened", min(12.0, 6.0 * reopens), f"citizen rejected the resolution {reopens} time(s)")

    # --- time ---------------------------------------------------------------
    unresolved = ctx.get("status") != "Resolved"
    if unresolved:
        resolution_target = ctx.get("resolution_target_hours")
        approved_extension_active = bool(ctx.get("approved_extension_active"))
        if approved_extension_active:
            pass  # Head-approved delay is quiet until its agreed follow-up time.
        elif resolution_target:
            ratio = max(float(ctx.get("age_hours") or 0), 0.0) / float(resolution_target)
            if ratio >= 1.0:
                time_pts = 4.0 + min(8.0, 8.0 * (ratio - 1.0))
                add("Past historical resolution target", time_pts, f"open {ctx.get('age_hours', 0):.0f}h against a text-matched historical median of {resolution_target:g}h")
            elif ratio >= 0.5:
                add("Approaching historical resolution target", 4.0 * (ratio - 0.5) / 0.5, f"{ratio*100:.0f}% of the text-matched historical median used")
        else:
            age_hours = max(float(ctx.get("age_hours") or 0), 0.0)
            if age_hours >= 48:
                add("Long open without comparable history", min(4.0, age_hours / 120.0), "no text-matched repair-time target is available yet")
        if not approved_extension_active:
            stale = float(ctx.get("since_update_hours") or 0)
            if stale > 120:
                add("No update", 5.0, f"no status update for {stale:.0f}h")
            elif stale > 48:
                add("No update", 3.0, f"no status update for {stale:.0f}h")

    # --- emergency / relief --------------------------------------------------
    if emergency:
        add("Verified emergency alert", 25.0, "verified emergency alert exists for this location")
    if ctx.get("actively_worked") and unresolved:
        add("Active officer work", -3.0, "officer updated the case in the last 24h")

    boost = max(-3.0, min(MAX_BOOST, sum(f["points"] for f in factors)))
    score = base_score(base, ctx.get("base_probs"), critical) + boost
    score = max(0.0, min(100.0, score))

    score_band = band(score)
    level = score_band
    label_adjustments = []
    # Critical is reserved for explicit emergencies.
    if level == "Critical" and not (critical or emergency or sig["danger"] >= 0.6):
        level = "High"
        label_adjustments.append("score_capped_without_explicit_emergency")
    if critical or emergency:
        level = "Critical"
        label_adjustments.append("explicit_critical_or_verified_emergency")
    if ctx.get("high_floor") and ORDER.index(level) < ORDER.index("High"):
        level = "High"
        label_adjustments.append("high_risk_safety_floor")
    # Never fall below the ML base class. The numeric score remains the raw
    # situational score; expose its band and any label adjustment separately.
    if ORDER.index(level) < ORDER.index(base):
        level = base
        label_adjustments.append("ml_base_priority_floor")

    top = sorted((f for f in factors if f["points"] > 0), key=lambda f: -f["points"])[:3]
    reason = f"{level} priority: ML base {base}; raw score {score:.1f} ({score_band} band)" + (
        "; " + ", ".join(f"{f['factor'].lower()} (+{f['points']:g})" for f in top) if top else "")
    return {
        "priority": level,
        "score": round(score, 1),
        "raw_score": round(score, 1),
        "score_band": score_band,
        "label_adjustments": label_adjustments,
        "factors": factors,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Database integration
# ---------------------------------------------------------------------------
def _load_state(complaint) -> dict:
    try:
        return json.loads(complaint.priority_factors) if complaint.priority_factors else {}
    except (ValueError, TypeError):
        return {}


def initial_state(priority_result: dict) -> str:
    """Serialise the ML result so later recomputation keeps the model's view."""
    return json.dumps({
        "base": {
            "priority": priority_result.get("base_priority") or priority_result.get("priority"),
            "probs": priority_result.get("probabilities") or {},
            "critical": bool(priority_result.get("critical_override")),
            "high_floor": bool(priority_result.get("high_risk_reasons")),
        },
        "score": None, "score_band": None, "label_adjustments": [], "factors": [],
    })


def refresh_priorities(db, complaints, commit=True) -> int:
    """Recompute priority for the given complaints (resolved ones are frozen).

    Uses a handful of batched queries, so it is safe to call before listing
    pages. Returns the number of complaints whose priority level changed.
    """
    from app.models.complaint import Complaint
    from app.models.complaint_event import ComplaintEvent
    from app.models.complaint_support import ComplaintSupport

    active = [c for c in complaints if c.status != "Resolved"]
    if not active:
        return 0

    cluster_ids = list({c.incident_cluster_id or c.complaint_id for c in active})
    members = (db.query(Complaint.incident_cluster_id, Complaint.complaint_id, Complaint.citizen_id,
                        Complaint.pincode, Complaint.area)
               .filter(Complaint.incident_cluster_id.in_(cluster_ids)).all())
    reporters, report_ct, places = defaultdict(set), defaultdict(int), defaultdict(set)
    for cid, _id, citizen, pin, area in members:
        report_ct[cid] += 1
        if citizen is not None:
            reporters[cid].add(citizen)
        places[cid].add(((pin or "").strip().lower(), (area or "").strip().lower()))
    supporters = defaultdict(set)
    for cid, citizen in (db.query(ComplaintSupport.incident_cluster_id, ComplaintSupport.citizen_id)
                         .filter(ComplaintSupport.incident_cluster_id.in_(cluster_ids)).all()):
        supporters[cid].add(citizen)

    ids = [c.complaint_id for c in active]
    update_types = ("status", "officer_action", "resolution_proof", "officer_assignment",
                    "smart_officer_assignment", "automatic_officer_assignment", "citizen_reopen")
    last_update, reopens = {}, defaultdict(int)
    for cid, etype, created in (db.query(ComplaintEvent.complaint_id, ComplaintEvent.event_type,
                                         ComplaintEvent.created_at)
                                .filter(ComplaintEvent.complaint_id.in_(ids),
                                        ComplaintEvent.event_type.in_(update_types)).all()):
        created = _aware(created)
        if created and (cid not in last_update or created > last_update[cid]):
            last_update[cid] = created
        if etype == "citizen_reopen":
            reopens[cid] += 1

    now = datetime.now(timezone.utc)
    changed = 0
    for c in active:
        cluster = c.incident_cluster_id or c.complaint_id
        state = _load_state(c)
        base_state = state.get("base") or {}
        base_priority = base_state.get("priority") or c.base_priority or (
            c.priority if c.priority in ORDER else "Medium")
        created = _aware(c.created_at) or now
        updated = last_update.get(c.complaint_id) or created
        text = " ".join(filter(None, [c.translated_title or c.title, c.translated_text or c.description]))
        resolution_sla = sla_info(c, db)
        result = compute_dynamic_priority({
            "base_priority": base_priority,
            "base_probs": base_state.get("probs"),
            "critical": base_state.get("critical", False),
            "high_floor": base_state.get("high_floor", False),
            "text": text,
            "department": c.predicted_department,
            "affected_count": len(reporters[cluster]) or 1,
            "support_count": len(supporters[cluster] - reporters[cluster]),
            "report_count": report_ct[cluster] or 1,
            "area_count": len(places[cluster]) or 1,
            "age_hours": (now - created).total_seconds() / 3600,
            "resolution_target_hours": resolution_sla["target_hours"],
            "approved_extension_active": resolution_sla["state"] == "Approved Extension",
            "since_update_hours": (now - updated).total_seconds() / 3600,
            "status": c.status,
            "reopen_count": reopens.get(c.complaint_id, 0),
            "emergency_alert": bool(c.verified_emergency),
            "actively_worked": c.status == "In Progress" and (now - updated).total_seconds() < 86400,
        })
        state.setdefault("base", {"priority": base_priority, "probs": {}, "critical": False, "high_floor": False})
        state["score"], state["score_band"] = result["score"], result["score_band"]
        state["label_adjustments"], state["factors"] = result["label_adjustments"], result["factors"]
        c.base_priority = base_priority
        c.priority_score = result["score"]
        c.priority_factors = json.dumps(state)
        c.priority_updated_at = now
        if result["priority"] != c.priority:
            old = c.priority
            c.priority = result["priority"]
            c.priority_reason = result["reason"]
            changed += 1
            db.add(ComplaintEvent(
                complaint_id=c.complaint_id, event_type="priority_change",
                title=f"Priority changed {old or 'n/a'} → {result['priority']}",
                detail=result["reason"], actor="CivicFlow Priority Engine"))
        else:
            # Keep the explanation synchronized with the latest score even when
            # the priority label itself did not change.
            c.priority_reason = result["reason"]
    if commit:
        db.commit()
    else:
        db.flush()
    return changed


def refresh_cluster(db, complaint, commit=True) -> int:
    """Recompute every unresolved complaint in this complaint's incident."""
    from app.models.complaint import Complaint
    cluster = complaint.incident_cluster_id or complaint.complaint_id
    rows = db.query(Complaint).filter(Complaint.incident_cluster_id == cluster).all()
    if all(r.complaint_id != complaint.complaint_id for r in rows):
        rows.append(complaint)
    return refresh_priorities(db, rows, commit=commit)


def priority_breakdown(complaint) -> dict:
    """API-friendly explanation of the current priority decision."""
    state = _load_state(complaint)
    base_state = state.get("base") or {}
    confidence = complaint.priority_confidence
    critical_override = bool(base_state.get("critical", False))
    return {
        "priority": complaint.priority,
        "score": complaint.priority_score,
        "raw_score": complaint.priority_score,
        "score_band": state.get("score_band"),
        "label_adjustments": state.get("label_adjustments", []),
        "ml_base_priority": base_state.get("priority") or complaint.base_priority,
        "ml_confidence": confidence,
        "needs_human_review": bool(
            confidence is not None and confidence < 0.50 and not critical_override
        ),
        "critical_override": critical_override,
        "high_risk_floor": bool(base_state.get("high_floor", False)),
        "reason": complaint.priority_reason,
        "factors": state.get("factors", []),
        "updated_at": complaint.priority_updated_at.isoformat() if complaint.priority_updated_at else None,
        "verified_emergency": bool(complaint.verified_emergency),
    }
