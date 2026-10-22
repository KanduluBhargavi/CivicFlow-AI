"""CivicFlow role/workflow regression check.

Runs against an isolated in-memory SQLite database. It does not touch the
project's PostgreSQL data. Usage from backend/: python tools/regression_check.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Isolated DB before importing app modules.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ.setdefault("SECRET_KEY", "regression-test-key")
os.environ.setdefault("ALGORITHM", "HS256")

BACKEND = Path(__file__).resolve().parents[1]
PROJECT = BACKEND.parent
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

# Keep the regression test self-contained even when this checker is run from a
# lightweight Python environment rather than the project's fully-installed venv.
# These stubs are used only for import-time dependencies; the tested workflow
# functions below do not call password/JWT/translation providers.
import types

security_stub = types.ModuleType("app.utils.security")
security_stub.hash_password = lambda value: f"hash:{value}"
security_stub.verify_password = lambda value, hashed: True
security_stub.create_access_token = lambda data: "test-token"
security_stub.decode_access_token = lambda token: {"sub": "test@test.local", "role": "citizen"}
sys.modules["app.utils.security"] = security_stub

auth_stub = types.ModuleType("app.utils.auth")
auth_stub.get_current_user = lambda: None
sys.modules["app.utils.auth"] = auth_stub

dependencies_stub = types.ModuleType("app.utils.dependencies")
dependencies_stub.get_current_user = lambda: None
dependencies_stub.get_current_department = lambda: None
sys.modules["app.utils.dependencies"] = dependencies_stub

ai_stub = types.ModuleType("app.services.ai_service")
ai_stub.detect_language = lambda text, language_hint=None: "en"
ai_stub.translate_text = lambda text, *args, **kwargs: {"success": True, "text": text} if kwargs.get("return_status") else text
ai_stub.predict_priority_details = lambda text: {"priority": "Low", "confidence": 1.0, "reason": "test"}
ai_stub.predict_department_details = lambda text: {"department": "Water Supply", "confidence": 1.0}
ai_stub.summarize_complaint = lambda text: text[:120]
ai_stub.get_department_id = lambda name, db: 1
ai_stub.suggest_reroute_department = lambda text: "Water Supply"
ai_stub.get_language_name = lambda code: "English" if code == "en" else str(code)
ai_stub.find_duplicate = lambda *args, **kwargs: {"is_duplicate": False, "classification": "none", "confidence": 0.0}
ai_stub.analyze_sentiment = lambda text: "Neutral"
ai_stub.normalize_language_code = lambda value: value or "unknown"
ai_stub.is_usable_english_translation = lambda original, translated: bool(translated)
sys.modules["app.services.ai_service"] = ai_stub

# Minimal jose stub for importing admin_routes.
jose_stub = types.ModuleType("jose")
class JWTError(Exception):
    pass
class _JWT:
    @staticmethod
    def decode(*args, **kwargs):
        return {"role": "admin", "sub": "admin@test.local"}
jose_stub.JWTError = JWTError
jose_stub.jwt = _JWT()
sys.modules["jose"] = jose_stub

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.department import Department
from app.models.user import User
from app.models.complaint import Complaint
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_event import ComplaintEvent
from app.models.complaint_support import ComplaintSupport
from app.models.complaint_escalation import ComplaintEscalation
from app.models.contact import Feedback
from app.routes.dashboard_routes import dashboard_stats, recent_complaints
from app.routes.complaint_routes import complaint_details, community_incidents
from app.routes.department_routes import (
    dashboard as department_dashboard,
    department_complaints,
    get_department_complaint,
    get_department_profile,
    update_department_profile,
    list_officers,
)
from app.routes.admin_routes import overview as admin_overview, geographic_hotspots
from app.services.escalation_service import desired_escalation
from app.services.officer_metrics import officer_metrics_for_ids
from app.schemas.department_schema import DepartmentProfileUpdate

PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"[PASS] {name}")
    else:
        FAIL.append((name, detail))
        print(f"[FAIL] {name}: {detail}")


def expect_http(name, status_code, fn):
    try:
        fn()
    except HTTPException as exc:
        check(name, exc.status_code == status_code, f"expected {status_code}, got {exc.status_code}")
    else:
        check(name, False, f"expected HTTP {status_code}, no exception raised")


def count_queries(engine, fn):
    counter = {"count": 0}
    def before_cursor_execute(*args, **kwargs):
        counter["count"] += 1
    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        result = fn()
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)
    return counter["count"], result


def seed(db):
    dept = Department(
        department_name="Water Supply",
        description="Water services",
        department_email="water@test.local",
        username="water",
        password="hash",
        is_active=True,
        ai_supported=True,
    )
    db.add(dept)
    db.flush()

    citizen = User(
        full_name="Citizen One", email="citizen1@test.local", phone="9000000001",
        password="hash", role="Citizen", state="Odisha", district="Kalahandi",
        area="Bhawanipatna", address="Lane 1", pincode="766001",
    )
    other_citizen = User(
        full_name="Citizen Two", email="citizen2@test.local", phone="9000000002",
        password="hash", role="Citizen", state="Odisha", district="Kalahandi",
        area="Bhawanipatna", address="Lane 2", pincode="766001",
    )
    officer = User(
        full_name="Dev Raj", email="devraj@test.local", phone="9000000003",
        password="hash", role="Officer", department_id=dept.department_id,
        state="Odisha", district="Kalahandi", specialization="water", max_active_cases=20,
        is_active=True,
    )
    db.add_all([citizen, other_citizen, officer])
    db.flush()

    now = datetime.now(timezone.utc)
    c1 = Complaint(
        citizen_id=citizen.user_id, department_id=dept.department_id,
        title="Dirty drinking water", description="drinking water is not clean",
        state="Odisha", district="Kalahandi", area="Bhawanipatna", address="Lane 1",
        pincode="766001", language="en", translated_text="drinking water is not clean",
        predicted_department="Water Supply", priority="High", ai_summary="Dirty drinking water",
        sentiment="Neutral", status="In Progress", assigned_at=now, in_progress_at=now,
        created_at=now,
    )
    c2 = Complaint(
        citizen_id=other_citizen.user_id, department_id=dept.department_id,
        title="No water supply", description="no water supply in locality",
        state="Odisha", district="Kalahandi", area="Bhawanipatna", address="Lane 2",
        pincode="766001", language="en", translated_text="no water supply in locality",
        predicted_department="Water Supply", priority="Medium", ai_summary="No water supply",
        sentiment="Neutral", status="Assigned", assigned_at=now, created_at=now,
    )
    c3 = Complaint(
        citizen_id=citizen.user_id, department_id=dept.department_id,
        title="Old resolved complaint", description="water leak fixed",
        state="Odisha", district="Kalahandi", area="Bhawanipatna", address="Lane 1",
        pincode="766001", language="en", translated_text="water leak fixed",
        predicted_department="Water Supply", priority="Low", ai_summary="Water leak",
        sentiment="Neutral", status="Resolved", assigned_at=now, resolved_at=now, created_at=now,
    )
    db.add_all([c1, c2, c3])
    db.flush()
    # Stable incident: c1 + c2; resolved c3 is separate.
    c1.incident_cluster_id = c1.complaint_id
    c2.incident_cluster_id = c1.complaint_id
    c3.incident_cluster_id = c3.complaint_id
    db.add(ComplaintAssignment(
        complaint_id=c1.complaint_id, officer_id=officer.user_id,
        assigned_by="Water Supply", assigned_at=now,
    ))
    db.add(ComplaintEvent(
        complaint_id=c1.complaint_id, event_type="officer_assignment",
        title="Assigned to Dev Raj", actor="Water Supply",
    ))
    db.commit()
    return dept, citizen, other_citizen, officer, c1, c2, c3


def run():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        dept, citizen, other, officer, c1, c2, c3 = seed(db)

        # Citizen
        stats = dashboard_stats(current_user=citizen, db=db)
        check("Citizen dashboard counts own complaints", stats == {"total_complaints": 2, "pending": 1, "resolved": 1}, str(stats))
        recent = recent_complaints(current_user=citizen, db=db)
        check("Citizen recent complaints are scoped to citizen", len(recent) == 2 and all(x["complaint_id"] in {c1.complaint_id, c3.complaint_id} for x in recent), str(recent))
        details = complaint_details(c1.complaint_id, current_user=citizen, db=db)
        check("Citizen sees assigned officer on own complaint", details.get("assigned_officer", {}).get("name") == "Dev Raj", str(details.get("assigned_officer")))
        not_mine = complaint_details(c2.complaint_id, current_user=citizen, db=db)
        check("Citizen cannot view another citizen complaint", not_mine.get("message") == "Complaint not found", str(not_mine))

        incident_query_count, incidents = count_queries(engine, lambda: community_incidents(current_user=citizen, db=db))
        check("Community incidents avoid N+1 query growth", incident_query_count <= 4, f"{incident_query_count} SQL queries")
        check("Community incident list still returns data", len(incidents) >= 1, str(incidents))

        # Department Head
        dept._actor_role = "manager"; dept._actor_name = dept.department_name; dept._actor_user_id = None
        manager_dash = department_dashboard(current_department=dept, db=db)
        check("Department Head sees full department workload", manager_dash["total"] == 3, str(manager_dash))
        manager_list = department_complaints(current_department=dept, db=db)
        check("Department Head sees all department complaints", len(manager_list) == 3, str(manager_list))
        manager_profile = get_department_profile(current_department=dept, db=db)
        check("Department Head profile remains department profile", manager_profile.get("viewer_role") == "manager", str(manager_profile))
        officer_query_count, officer_rows = count_queries(engine, lambda: list_officers(current_department=dept, db=db))
        check("Officer accountability list uses bounded batched queries", officer_query_count <= 6, f"{officer_query_count} SQL queries")
        check("Officer accountability still returns officer", len(officer_rows) == 1 and officer_rows[0]["name"] == "Dev Raj", str(officer_rows))

        # Officer
        dept._actor_role = "officer"; dept._actor_name = officer.full_name; dept._actor_user_id = officer.user_id
        officer_dash = department_dashboard(current_department=dept, db=db)
        check("Officer dashboard only counts assigned cases", officer_dash["total"] == 1, str(officer_dash))
        officer_list = department_complaints(current_department=dept, db=db)
        check("Officer complaint list only contains own assignments", len(officer_list) == 1 and officer_list[0]["complaint_id"] == c1.complaint_id, str(officer_list))
        officer_details = get_department_complaint(c1.complaint_id, current_department=dept, db=db)
        check("Officer can open complaint assigned to them", officer_details["complaint_id"] == c1.complaint_id, str(officer_details.get("complaint_id")))
        expect_http("Officer cannot open unassigned/other complaint", 403, lambda: get_department_complaint(c2.complaint_id, current_department=dept, db=db))
        officer_profile = get_department_profile(current_department=dept, db=db)
        check("Officer profile shows individual identity", officer_profile.get("officer_name") == "Dev Raj" and officer_profile.get("department_name") == "Water Supply", str(officer_profile))
        expect_http("Officer cannot edit department profile", 403, lambda: update_department_profile(DepartmentProfileUpdate(department_name="Changed", description=None), current_department=dept, db=db))

        # Operational maturity features
        from datetime import timedelta
        original_created = c2.created_at
        original_priority = c2.priority
        c2.created_at = datetime.now(timezone.utc) - timedelta(hours=100)
        c2.assigned_at = c2.created_at
        c2.priority = "Medium"
        level, reason = desired_escalation(c2)
        check("Escalation hierarchy derives SLA level", level == 2 and bool(reason), f"level={level}, reason={reason}")
        c2.created_at = original_created
        c2.assigned_at = original_created
        c2.priority = original_priority

        history = officer_metrics_for_ids(db, [officer.user_id]).get(officer.user_id, {})
        check("Officer performance uses recorded history", "resolution_rate" in history and "sla_compliance_rate" in history, str(history))

        c1.latitude, c1.longitude = 20.4640, 85.8793
        c2.latitude, c2.longitude = 20.4644, 85.8798
        db.commit()
        hotspots = geographic_hotspots({}, db=db)
        check("Hotspot analytics uses stored coordinates", len(hotspots) >= 1 and hotspots[0]["complaint_count"] >= 2, str(hotspots[:1]))

        # Admin aggregate logic
        admin = admin_overview({}, db=db)
        check("Admin overview sees system totals", admin["total_complaints"] == 3 and admin["total_officers"] == 1 and admin["total_users"] == 2, str(admin))

        # Cleanup/static expectations
        department_source = (PROJECT / "backend/app/routes/department_routes.py").read_text(encoding="utf-8")
        check("Obsolete repair-language endpoint removed", 'repair-language' not in department_source)
        check("Obsolete manual-translation endpoint removed", 'manual-translation' not in department_source)
        root_md = [p.name for p in PROJECT.glob("*.md")]
        check("Single root README retained", root_md == ["README.md"], str(root_md))

    finally:
        db.close()

    print(f"\nRegression result: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for name, detail in FAIL:
            print(f" - {name}: {detail}")
        raise SystemExit(1)


if __name__ == "__main__":
    run()
