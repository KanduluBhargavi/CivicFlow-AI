# Translation Feedback and Correction Workflow

## What it does

- Citizens can open their own complaint details and report a wrong translation, misleading English summary, or title/location translation issue.
- The report stores the complaint reference, original text snapshot, English translation snapshot, optional suggested correction, and the citizen's explanation.
- Administrators get a **Translation Reviews** tab, can inspect the report, add a reviewer note, and mark it Pending, Reviewed, Accepted, or Rejected.
- The new API is protected: only the complaint owner can submit a report, and only an administrator token can list/review reports.
- An accepted suggestion is recorded as accepted feedback; it does **not** silently overwrite the original complaint or ML training data. Corrections should be verified before operational text or training data is changed.

## API

- `POST /translation-feedback/complaints/{complaint_id}` — citizen submits a report.
- `GET /translation-feedback/admin?status=Pending` — administrator lists reports; `status` is optional.
- `PATCH /translation-feedback/admin/{feedback_id}` — administrator updates status and reviewer note.

## Database

The `translation_feedback` table is created by the project's existing `Base.metadata.create_all()` startup path because the model is registered in `app/main.py`. Existing complaint and user records are not rewritten.

## Test

From the `backend` directory, run:

```bash
python training/test_translation_feedback_workflow.py
python -m py_compile app/models/translation_feedback.py app/routes/translation_feedback_routes.py app/main.py
```

Also hard-refresh the citizen complaint details page and administrator dashboard after updating the files.
