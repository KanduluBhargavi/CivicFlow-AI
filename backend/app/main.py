from fastapi import FastAPI, Request, HTTPException
import os
from app.database import engine, Base
from app.routes.complaint_routes import router as complaint_router
from app.routes import support_routes
from app.routes.voice_routes import router as voice_router

from fastapi.middleware.cors import CORSMiddleware
#import models
from app.models.user import User
from app.models.department import Department
from app.models.complaint import Complaint
from app.models.complaint_event import ComplaintEvent
from app.models.complaint_assignment import ComplaintAssignment
from app.models.complaint_support import ComplaintSupport
from app.models.complaint_escalation import ComplaintEscalation
from app.models.in_app_notification import InAppNotification
from app.models.complaint_deletion import ComplaintDeletion
from app.models.translation_feedback import TranslationFeedback
from app.models.complaint_delay_request import ComplaintDelayRequest

from app.routes.admin_routes import router as admin_router
from app.routes.user_routes import router as user_router
from fastapi.staticfiles import StaticFiles
from app.routes.dashboard_routes import router as dashboard_router
from app.routes import department_routes
from app.routes.contact_routes import router as contact_router 



from app.config import validate_production_security
validate_production_security()

# Database schema changes are applied by versioned Alembic migrations before
# the ASGI server starts. The application process never mutates schema.

def _normalize_existing_locations():
    """One-time-safe cleanup for legacy free-text location values.

    Dropdowns prevent new variants; this normalizes older records such as
    Odhisa/odisha and lower-case district names so analytics do not split them.
    """
    from app.database import SessionLocal
    from app.utils.location_normalization import normalize_location, normalize_state
    db = SessionLocal()
    try:
        changed = False
        for user in db.query(User).all():
            state, district = normalize_location(user.state, user.district)
            if user.state != state or user.district != district:
                user.state, user.district = state, district
                changed = True
        for dept in db.query(Department).all():
            state = normalize_state(getattr(dept, "state", None))
            if getattr(dept, "state", None) != state:
                dept.state = state
                changed = True
        if changed:
            db.commit()
    finally:
        db.close()


if os.getenv("RUN_STARTUP_DATA_REPAIRS", "false").lower() == "true":
    _normalize_existing_locations()


def _backfill_incident_clusters_once():
    from app.database import SessionLocal
    from app.services.incident_service import backfill_incident_clusters
    db = SessionLocal()
    try:
        backfill_incident_clusters(db)
    finally:
        db.close()


if os.getenv("RUN_STARTUP_DATA_REPAIRS", "false").lower() == "true":
    _backfill_incident_clusters_once()

def _preload_semantic_model():
    """Load/download SBERT during backend startup, not on complaint page load."""
    from app.services.incident_service import _get_sbert_model

    model = _get_sbert_model()
    if model is None:
        print(
            "[SBERT] backend will run, but semantic similar-complaint matching "
            "is temporarily unavailable.",
            flush=True,
        )


def _schedule_semantic_model_preload():
    """Warm the optional semantic model without delaying API startup/readiness."""
    import threading
    threading.Thread(
        target=_preload_semantic_model,
        daemon=True,
        name="semantic-model-preload",
    ).start()


# Loading SBERT at every cold start competes with the first dashboard requests
# for CPU and disk, while most sessions never open semantic matching. The first
# semantic-match request loads it on demand. Set PRELOAD_SEMANTIC_MODEL=true to
# opt into background warming on machines dedicated to CivicFlow.
if os.getenv("PRELOAD_SEMANTIC_MODEL", "false").lower() == "true":
    _schedule_semantic_model_preload()


def _start_priority_refresh_loop():
    """Re-score open complaints periodically so priority rises as time passes,
    even if nobody opens a dashboard. Disable with PRIORITY_REFRESH_MINUTES=0."""
    import threading, time
    minutes = float(os.getenv("PRIORITY_REFRESH_MINUTES", "15"))
    if minutes <= 0:
        return

    def loop():
        from app.database import SessionLocal
        from app.services.priority_engine import refresh_priorities
        while True:
            time.sleep(minutes * 60)
            db = SessionLocal()
            try:
                refresh_priorities(db, db.query(Complaint).filter(Complaint.status != "Resolved").all())
            except Exception as exc:  # never let the monitor kill the API
                print(f"[priority-refresh] skipped: {exc}", flush=True)
                db.rollback()
            finally:
                db.close()

    threading.Thread(target=loop, daemon=True, name="priority-refresh").start()


_start_priority_refresh_loop()


def _start_auto_assignment_loop():
    """Assign eligible staff when the department-head assignment timer expires."""
    import threading, time
    seconds = max(15, int(os.getenv("OFFICER_ASSIGNMENT_CHECK_SECONDS", "60")))

    def loop():
        from app.services.automatic_assignment import run_assignment_cycle, run_delay_followup_cycle
        while True:
            time.sleep(seconds)
            try:
                run_assignment_cycle()
                run_delay_followup_cycle()
            except Exception as exc:  # a transient failure must not stop the API
                print(f"[automatic-assignment] cycle failed: {exc}", flush=True)

    threading.Thread(target=loop, daemon=True, name="automatic-officer-assignment").start()


_start_auto_assignment_loop()


app=FastAPI(
    title="CivicFlow AI",
    version="1.0.0"
)

cors_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:5500,http://localhost:5500"
    ).split(",")
    if origin.strip()
]
allow_local_dev_origin_regex = (
    r"^https?://(localhost|127\.0\.0\.1|10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})(:\d+)?$"
    if os.getenv("APP_ENV", "development").lower() != "production"
    else None
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=allow_local_dev_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    return response
# Uploads are NOT public static files: a valid signed token (issued inside
# already-authorised API responses) is required for every download.
from fastapi.responses import FileResponse
from app.utils.media import verify_media_token

_UPLOAD_ROOT = os.path.abspath("uploads")


@app.get("/uploads/{filename}", include_in_schema=False)
def serve_upload(filename: str, t: str | None = None):
    if filename != os.path.basename(filename) or filename.startswith("."):
        raise HTTPException(status_code=404, detail="Not found")
    if not verify_media_token(filename, t):
        raise HTTPException(status_code=403, detail="Link expired or invalid")
    full = os.path.abspath(os.path.join(_UPLOAD_ROOT, filename))
    if os.path.dirname(full) != _UPLOAD_ROOT or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="Not found")
    resp = FileResponse(full)
    resp.headers["Cache-Control"] = "private, max-age=300"
    return resp

app.include_router(user_router)
app.include_router(complaint_router)
app.include_router(dashboard_router)
app.include_router(admin_router)
app.include_router(department_routes.router)
app.include_router(contact_router)
app.include_router(support_routes.router)
app.include_router(voice_router)


@app.get("/")
def home():
    return {
        "message": "Welcome to CivicFlow AI Backend",
        "status":"Running Successfully"
    }

@app.get("/health")
def health():
    from sqlalchemy import text
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception:
        raise HTTPException(status_code=503, detail="Database health check failed")
    finally:
        db.close()
