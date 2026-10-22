# Officer Notification Centre

## Included
- Persistent database-backed notifications with created/read timestamps.
- Officer-scoped notifications for assignments and reassignments.
- Manager-visible department notifications for SLA-at-risk/breached complaints.
- Officer and department-manager notifications for citizen resolution confirmation/reopen events.
- Read/unread count, mark-one-read and mark-all-read API endpoints.
- Dashboard bell uses the persistent inbox and shows the latest 30 entries (20 rendered in the menu).
- SLA reminders are materialized idempotently using a stable dedupe key when the inbox is refreshed.

## Database
`in_app_notifications` is created by SQLAlchemy `Base.metadata.create_all()` because the model is imported by `app.main`. Restart the backend after copying files. For an environment with `AUTO_SCHEMA_SETUP=false`, apply a proper migration before using this feature.

## API
- `GET /department/notifications`
- `PATCH /department/notifications/{notification_id}/read`
- `PATCH /department/notifications/read-all`

Every endpoint scopes reads/writes to the current officer or department manager. Do not remove these authorization filters.

## Test
From `backend/training`, run `python test_notification_center.py`, then run the existing three ML regression suites and manually test assigning/reassigning a complaint and reopening a resolved complaint.
