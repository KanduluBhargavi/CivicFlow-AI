# Emerging Incident Alerts

## Why this feature exists
A burst of related complaints can indicate that an individual service failure is affecting multiple people. The admin Hotspots page now shows clusters that meet a transparent 24-hour threshold, helping staff investigate a growing issue earlier.

## Thresholds
- 3 or more linked complaints within the last 24 hours; or
- 2 or more linked complaints in 24 hours when at least one recent complaint is marked Critical.

The API uses the persisted incident cluster IDs already assigned by CivicFlow. It does not create a new ML model and does not label an alert as a confirmed emergency. The admin sees report counts, unresolved count, highest priority, latest report time, location and the reason the threshold fired.

## Important limitations
- This is an explainable rule-based signal, not proof of causation or a prediction that an incident will happen.
- It depends on the existing duplicate/incident clustering quality. Incorrect cluster links can produce misleading alerts.
- Reports without reliable location or correct cluster links may not be grouped as expected.
- Urgent single complaints continue to be handled by the existing priority/escalation workflow; this feature is for patterns across multiple reports.

## Translation feedback decision
The citizen translation-feedback panel and its API registration were removed because citizens should not be asked to verify an English translation they cannot understand, and department officers may not understand the source language either. Existing database data is not dropped; the old table, if present, is left untouched.

## Test
From `backend` with the project's Python environment:

```bash
python training/test_emerging_incident_alerts.py
python -m py_compile app/routes/admin_routes.py app/main.py
```


## Direct department alert delivery
The department manager dashboard now calls `/department/emerging-incident-alerts`, which returns only alert clusters containing complaints routed to that department. Managers can see alerts directly rather than waiting for an administrator to forward them. The endpoint is authenticated and department-scoped. Officer accounts do not receive the department-wide panel; the endpoint limits officer results to assigned complaints if accessed. The admin-wide overview remains available for cross-department oversight.

## Geographic label safety
Hotspot district names are currently derived from complaint records, not from a verified administrative-boundary dataset. The hotspot API now includes `district_verified: false` and a `district_data_warning`; cells containing conflicting district values are explicitly flagged. This avoids presenting the stored district as geographically verified. Correct boundary-based district validation requires a reliable Odisha district-boundary dataset and a geospatial point-in-polygon check; it should not be guessed from the map screenshot.
