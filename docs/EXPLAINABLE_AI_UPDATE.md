# CivicFlow Explainable AI Update

## What changed

This update connects the existing dynamic priority explanation to the department complaint-details page. It does not retrain either ML model and does not add database columns.

- The existing `priority_analysis` API payload now includes ML confidence, a human-review flag derived from the existing `< 0.50` confidence rule, and persisted critical/high-risk flags.
- The department complaint details page shows original ML priority, final priority, dynamic urgency score, model confidence, the current explanation, recorded factors and point contributions, label adjustments, and saved safety/emergency indicators.
- Dynamic content is inserted with DOM `textContent`, not interpolated into HTML.
- The panel has responsive and dark-mode styling.
- A dependency-free static check was added at `backend/training/test_explainable_ai_ui.py`.

## Apply the update

1. Stop the backend with `Ctrl+C`.
2. Back up the current `D:\CivicFlow-AI` folder.
3. Extract this ZIP into a separate temporary folder.
4. Copy the following files from the extracted project into the matching locations in your current project:
   - `backend/app/services/priority_engine.py`
   - `frontend/department_complaint_details.html`
   - `frontend/js/department_details.js`
   - `frontend/css/department_details.css`
   - `backend/training/test_explainable_ai_ui.py`
   - `docs/EXPLAINABLE_AI_UPDATE.md`
5. Do not replace your `.env`, virtual environment, model cache, or local database.
6. Restart the backend and hard-refresh the browser (`Ctrl+F5`). Open a department complaint details page.

## Checks

From `D:\CivicFlow-AI\backend\training`, run:

```powershell
python test_explainable_ai_ui.py
python test_priority_engine.py
python test_priority_model.py
python test_department_routing.py
python test_notification_center.py
```

The static Explainable AI checks and priority-engine regression suite passed in the build environment. The remaining checks should be run in your local virtual environment after applying the update.

## Interpretation notes

- The dynamic score band and final priority label can differ because the priority engine applies a minimum-label floor.
- `Emergency verified` is shown only when the stored `verified_emergency` flag is true. Text-based critical/high-risk flags are labeled separately and are not described as department-verified emergencies.
- The human-review flag is derived from the saved ML confidence and the existing rule: confidence below 0.50 and no saved critical override. It is a recommendation, not proof that an officer has reviewed the case.
- Older complaints may have incomplete saved safety flags if those flags were not persisted when the complaint was originally created.
