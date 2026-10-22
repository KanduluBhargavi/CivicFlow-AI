# CivicFlow v14 remediation notes

## Implemented
- Removed credentials in `backend/.env` and all sample user-uploaded images from the release ZIP. Rotate any credentials previously present in v13.
- Added 200-record default pagination (`limit` up to 1000 and `offset`) to citizen and department complaint lists, retaining the original JSON-array response. Integrators should use `?limit=200&offset=200` for additional pages.
- Moved legacy location normalization and incident backfill behind `RUN_STARTUP_DATA_REPAIRS=true` instead of blocking every backend startup. Existing installs that need repair should enable this once in a maintenance window.
- Added optional production security validation; production requires a strong application secret, disabled OTP development mode, and shared Redis state.
- Added Redis-backed OTP challenge and login failure storage when `REDIS_URL` is configured; Docker Compose includes Redis.
- Made automatic schema creation/migration configurable. Production deployment must provision its schema before setting `APP_ENV=production` with `AUTO_SCHEMA_SETUP=false`.

## Outstanding engineering work (not claimed fixed)
- Translation still executes synchronously on submission; a persistent worker queue and API-compatible status lifecycle require integration testing.
- Semantic cluster membership can differ from a direct complaint-to-complaint match; UX should label incident membership separately from direct matches.
- District-coordinate accuracy and all UI breakpoints still need real-world/browser verification.
- Full Alembic baseline and migration scripts are not yet included; current schema initializer is still used in development.
- ML accuracy has not been re-benchmarked and production load/security tests have not been completed.

## Run
Copy `.env.docker.example` to `.env`, set a unique `SECRET_KEY` and database password, then `docker compose up --build -d`. Do not commit or distribute `.env`.
