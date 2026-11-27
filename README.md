# CivicFlow-AI

**A prototype civic grievance management platform with ML-assisted department routing and priority classification.** Citizens can submit and track complaints; departments and officers can manage cases; administrators can review operations and incident patterns.

> CivicFlow is a portfolio prototype. Its priority labels include synthetic/curated supervision and limited user-reviewed corrections. Priority predictions are decision support, not validated service-level decisions.

## What it does

- **Citizen portal:** account registration and login, location-aware complaint submission with optional media, status tracking, updates, resolution confirmation or reopen, and satisfaction ratings.
- **Department routing:** ML predicts one of eight CivicFlow departments. Staff can review and correct the route.
- **Priority support:** ML predicts Low, Medium, or High. Explicit high-risk and life-safety checks can raise cases to High or Critical. Officers should verify the complaint details.
- **Incident handling:** similar-meaning suggestions, persisted incident links, affected-citizen support, locality summaries, and separate geographic views. Text similarity is pairwise; a linked incident group is not proof that every report describes the same event.
- **Department and officer workflows:** department queues, officer assignment and workload context, action history, service targets, escalations, resolution evidence, and audit events.
- **Admin tools:** user and department management, operational dashboards, CSV/PDF reports, notification and escalation oversight, and coordinate-based hotspots.
- **Language and accessibility:** original complaint text is retained; non-English submissions use the translation flow; voice complaint and listen-back features support accessibility.

## Technology

- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **Database:** PostgreSQL; Redis is included in the Docker Compose stack
- **Frontend:** HTML, CSS, and JavaScript
- **ML/NLP:** scikit-learn, TF-IDF text features, calibrated or probabilistic classifiers, Sentence-BERT semantic matching, and language/translation utilities
- **Operations:** Docker Compose, Nginx, GitHub Actions workflows
- **Location:** administrative boundary and pincode data; geographic hotspot views use stored coordinates only

## ML models and data

### Department routing

The model predicts CivicFlow’s existing eight operational departments. Training combines `dataset/department_dataset.csv` with **4,500** mapped complaint rows from `dataset/hf_public_grievance_candidate.csv`, sourced from [hackermango/Public_Grievance_Dataset](https://huggingface.co/datasets/hackermango/Public_Grievance_Dataset). Nine compatible source categories map to CivicFlow departments; unmapped categories are excluded. Grouped cross-validation selects the source weight, and the reported holdout contains CivicFlow examples only.

- Model: Logistic Regression
- Selected HF source weight: 1.0 relative to the CivicFlow source
- Mapped source labels: Roads and Public Works → Roads & Transport; Public Transport → Roads & Transport; Electricity and Street Lighting → Electricity; Municipal Services → Municipal Corporation; Sanitation and Solid Waste → Sanitation; Water Supply and Irrigation → Water Supply; Public Health and Hospitals → Healthcare; Education and Scholarships → Education; Police and Public Safety → Police. Other HF labels are excluded.
- Grouped CV Macro-F1: **90.17%**
- CivicFlow-only holdout: **94.33% accuracy / 93.40% Macro-F1**

### Priority classification

Priority inference uses complaint text with word and character TF-IDF plus urgency features, including a short-duration signal. Training uses the in-domain `priority_dataset.csv`, training-only priority mappings from `civicdex_adapted.csv` and `annotated_complaints_with_severity.csv`, and user-feedback rows from `priority_supplement.csv`. External examples that overlap held-out complaint groups are excluded from those training folds. Status and `days_open` are not priority inputs because they describe post-submission outcomes.

- Model: SGDClassifier with log-loss
- Current grouped CV: **78.16% accuracy / 77.37% Macro-F1**
- In-domain grouped holdout: **79.86% accuracy / 78.87% Macro-F1**
- The supplement contains two earlier reviewed examples, a reviewed correction that a five-minute water interruption is Low, and two explicitly marked wording paraphrases of that correction. Paraphrases are training augmentation, not independent citizen reports.
- Critical is handled by a separate transparent safety layer; it is not a learned priority class.

The in-domain priority labels include synthetic or curated supervision and have not been independently validated against operational outcomes. CivicDex urgency and CivicComp severity are mapped labels from different datasets. Metrics therefore describe these evaluation splits, not guaranteed accuracy on future real complaints. The model is suitable for a prototype and human-reviewed decision support.

### Data provenance

- Hugging Face department source: [hackermango/Public_Grievance_Dataset](https://huggingface.co/datasets/hackermango/Public_Grievance_Dataset). The project copy and department mapping are in `dataset/`.
- CivicComp annotated severity source page: [Kaggle dataset](https://www.kaggle.com/datasets/shyamtripathi373/civiccomp-hien-hindienglish-civic-complaints). Its source page indicates CC BY-SA 4.0; verify attribution and license terms before redistribution.
- CivicDex data is retained in `dataset/civicdex_adapted.csv`; check the source’s current terms before redistributing.
- Do not describe synthetic, mapped, or paraphrased rows as complaints collected by CivicFlow.

## Run locally on Windows

From the project root:

```powershell
cd D:\CivicFlow-AI\backend
py -m venv venv                 # only if the venv does not exist
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload
```

Run the frontend in a second PowerShell window from the project root:

```powershell
cd D:\CivicFlow-AI
python .\serve_frontend.py
```

Open `http://127.0.0.1:5500`. The API runs at `http://127.0.0.1:8000`; its health endpoint is `/health`. English complaints skip translation. Translation providers and credentials are configured through environment variables; BHASHINI calls require approved credentials, and the free Google web fallback has no production SLA.

Configure database access and Admin credentials in the local environment. Generate an Admin password hash from `backend/` with `python tools/create_admin_hash.py`. Never commit `.env` files, secrets, or production credentials.

## Retrain and check the models

From the project root, using the existing backend virtual environment:

```powershell
.\backend\venv\Scripts\python.exe .\backend\training\train_department_model.py
.\backend\venv\Scripts\python.exe .\backend\training\train_priority_model.py
```

Both scripts save model files under `models/` and metrics/confusion matrices under `models/reports/`. Restart the backend after retraining: on startup it detects changed priority artifacts and re-scores open complaints; resolved complaints remain frozen. For a combined training run, use `train_ml_models.py`. Inference checks include:

```powershell
.\backend\venv\Scripts\python.exe .\backend\training\test_department_routing.py
.\backend\venv\Scripts\python.exe .\backend\training\test_priority_model.py
.\backend\venv\Scripts\python.exe .\backend\training\test_ml_stack.py
```

`backend/tools/regression_check.py` covers broader application workflows and may require a working local database configuration.

## Run with Docker Compose

```powershell
Copy-Item .env.docker.example .env.docker
# Edit .env.docker: set strong local secrets, database password, and Admin values.
docker compose --env-file .env.docker up --build
```

Open `http://localhost:8080`. Docker starts PostgreSQL, Redis, FastAPI, and the Nginx frontend. Do not use example/default secrets for a public deployment. Configure production CORS, HTTPS, persistent storage, backups, monitoring, email delivery, and secret management before exposing the service publicly.

**Model files:** `*.pkl` is ignored by Git. The trained artifacts must either be included in the deployment through an intentional artifact workflow or regenerated during the deployment build; a normal `git add .` will not include them.

## Project layout

```text
backend/       FastAPI application, migrations, training and checks
frontend/      Citizen, department, officer and admin interfaces
dataset/       Training data and provenance notes
models/        Local model artifacts, manifests and evaluation reports
.github/       CI workflow configuration
docker-compose.yml  Local container stack
serve_frontend.py  Simple frontend server for local use
```

The canonical API entry point is `backend/app/main.py`. Database schema changes are managed with Alembic migrations. The project is a prototype: complete security, privacy, deployment, and operational reviews before using it for real civic-service decisions.
