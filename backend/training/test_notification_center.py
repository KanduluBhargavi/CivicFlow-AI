"""Static regression checks for persistent notification-centre integration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
checks = {
    "persistent notification model": ROOT / "backend/app/models/in_app_notification.py",
    "notification service": ROOT / "backend/app/services/in_app_notifications.py",
    "notification routes": ROOT / "backend/app/routes/department_routes.py",
    "citizen feedback notification hook": ROOT / "backend/app/routes/complaint_routes.py",
    "notification inbox UI": ROOT / "frontend/js/department_dashboard.js",
}
for label, path in checks.items():
    assert path.exists(), f"Missing {label}: {path}"
    source = path.read_text(encoding="utf-8")
    assert source.strip(), f"Empty {label}: {path}"
    print(f"PASS | {label}")

route_source = checks["notification routes"].read_text(encoding="utf-8")
for marker in ("notifications/{notification_id}/read", "notifications/read-all", "def department_notifications", "complaint_assigned", "sla_breached"):
    assert marker in route_source, f"Missing notification behavior: {marker}"
complaint_source = checks["citizen feedback notification hook"].read_text(encoding="utf-8")
assert "citizen_reopen" in complaint_source and "create_notification" in complaint_source
ui_source = checks["notification inbox UI"].read_text(encoding="utf-8")
assert "markNotificationRead" in ui_source and "markAllNotificationsRead" in ui_source
print("Notification centre static regression checks passed.")
