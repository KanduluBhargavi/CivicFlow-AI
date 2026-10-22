# Department incident map update

- Department managers/heads now see their own emerging incident alerts on a Leaflet map directly in the department dashboard, as well as in the alert list.
- The map includes detailed-street and humanitarian tile styles, zoom and scale controls, priority-colored pulsing markers, and popups with counts and a location-accuracy note.
- Only alert clusters with usable latitude/longitude from recent complaint records receive map markers. Alerts without coordinates remain visible in the list and are explicitly not pinned.
- Both admin and department alert APIs include approximate coordinates averaged from recent located complaints. These are cluster visualizations, not verified addresses or administrative-boundary lookups.
- Admin hotspot map now defaults to a more detailed CARTO Voyager basemap with a humanitarian tile option, zoom controls, scale, and district-data warning in popups.

## Validation

Run `python -m py_compile backend/app/routes/admin_routes.py backend/app/routes/department_routes.py`, `node --check frontend/js/admin_dashboard.js`, `node --check frontend/js/department_dashboard.js`, and the existing emerging-alert and notification-centre regression tests. Browser verification is still required for actual tile loading and role-specific dashboard behavior.
