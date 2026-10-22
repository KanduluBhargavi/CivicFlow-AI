# CivicFlow AI — Functional Audit and Follow-up Plan (18 October 2026)

## Changes in this patch

1. Officer creation now validates name, email format, password length (8–128 characters), and case capacity on both the browser and API. The server normalizes email before duplicate checks.
2. Department managers can permanently delete officers. Deletion is refused while unresolved complaints are assigned to that officer; reassign/resolve them first. Historical ComplaintEvent rows remain, but assignment records and officer performance history derived from those assignments are removed.
3. Department dashboard Latest Activity now reads the newest persisted complaint event, rather than sorting by complaint submission time. Assignment/status/reopen events can therefore appear as the latest action.
4. Sentence-like/long complaint titles are excluded from the ML input to avoid contradictory title text overriding the verified description. Their operational display title is shortened to a neutral department/issue label, including for legacy rows. The citizen's original title and full description remain stored; this does not rewrite the original complaint.
5. New citizen complaint titles are limited to 3–100 characters at both UI and API. Full details belong in the description.
6. Deactivated officers are blocked at login and on department API requests, so a previously issued token does not bypass deactivation.

## Verified observations from static review

- Department model artifacts warn when loaded with a scikit-learn version different from the version used to serialize them. The app currently runs with 1.9.1 and saved department artifacts report 1.8.0. Pin the training/runtime versions together or retrain and validate the department model under the selected version before production.
- `backend/app/routes/user_routes.py` contains a hard-coded admin email/password (`admin@civicflow.com` / `admin123`). This remains a high-priority security issue requiring a separate, deliberate migration to environment-configured credentials or a persisted hashed admin account. I have not silently removed it in this patch because doing so without updating your local environment could lock you out of the admin dashboard. Never deploy the default credential publicly.
- `backend/app/services/otp_service.py` has a development fallback pepper. Production must set a unique `OTP_PEPPER`; the production validator currently requires a strong `SECRET_KEY` and Redis but should also require `OTP_PEPPER`.
- `backend/app/config.py` already validates `SECRET_KEY` in production, but deployment configuration still needs a secret-rotation and environment-file hygiene check.
- Department `change-password` currently returns an ordinary JSON message for an incorrect old password in one branch rather than an HTTP 400/401. Correct this for consistent client handling.
- The department dashboard Latest Activity card previously used `created_at`, so it could not show a later assignment/status event. Fixed in this patch.
- Translation providers can return fluent but semantically imperfect text. Keep original citizen text immutable, show the full English processing copy separately, and add a user/officer correction/report-translation control before relying on it for high-impact decisions.

## Recommended next features (priority order)

1. **Explainable decision card:** show predicted department, base ML priority, final priority, confidence, semantic/keyword signals, safety overrides and why a human-review flag was raised.
2. **Officer notification centre:** persist unread notifications for assignments, reassignment, SLA approaching/breached, citizen reopen and department notes; link each notification to the complaint.
3. **Translation feedback/correction:** let staff flag a translation as inaccurate and record a corrected English processing copy while preserving the citizen's original text and audit trail.
4. **Duplicate/related complaint review queue:** show similarity, location agreement and matching incident ID, with human confirmation for medium-confidence matches.
5. **Audit log search/export:** filter complaint events by actor, event type, department and date; do not delete the audit events when deleting an officer.
6. **Department SLA analytics:** median resolution time, overdue rate, reopen rate and citizen satisfaction, segmented by priority and department.
7. **Model monitoring:** collect reviewed final outcomes and report per-class precision/recall, calibration, translation failures, override rates and department-routing confusion.

## Validation still required on the user's Windows environment

- Run `python test_priority_model.py`, `python test_priority_engine.py`, and `python test_department_routing.py`.
- Test officer create with empty name/email/password, malformed email, password shorter than 8 characters, duplicate email, and valid input.
- Test deleting an officer with an active complaint (must return 409), then reassign it and delete (must succeed).
- Assign a complaint and confirm the department dashboard Latest Activity displays the assignment event and correct relative time.
- Submit a long sentence-like title with a translated description containing negation. Confirm the display title is short, full original title remains available, and the priority/department prediction uses the description rather than the contradictory title.
