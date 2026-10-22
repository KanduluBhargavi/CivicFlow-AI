# CivicFlow-AI

**AI-Powered Multilingual Public Grievance Routing, Priority Classification and Incident Management Platform**

CivicFlow-AI is a full-stack civic grievance platform where citizens can submit complaints, departments can route and manage cases, individual officers can act on assigned work, and administrators can monitor the system.

## Current feature set

### Citizen
- Register/login and submit grievances with location and optional media.
- English complaints are processed directly; non-English complaints use the multilingual translation pipeline.
- Track complaint status, department receipt and individual officer assignment.
- View complaint-specific notification updates.
- Confirm a resolution or reopen the complaint when the issue still exists.
- Give a **1–5 satisfaction rating tied to a confirmed resolved complaint**.
- See nearby community incidents and use **I'm affected too** instead of filing a duplicate.
- Open a dedicated **Incident Details** page showing linked-report count, affected citizens, status distribution and community impact.

### AI / ML
- Department routing across 8 civic departments.
- Priority classification using Low / Medium / High, with explicit safety rules for Critical hazards.
- Word + character TF-IDF features.
- Department model held-out accuracy: **93.93%**, macro-F1: **93.41%**.
- Priority model held-out accuracy: **82.41%**, macro-F1: **75.25%**.
- AI summary, sentiment/frustration signal, duplicate/incident detection and explainable related-complaint reasons.
- Sentiment is displayed as context only and does **not** determine operational priority.

### Incident intelligence
- Persisted incident clusters so pages do not rebuild the complete duplicate graph on each load.
- Stable cluster membership.
- Related-complaint explanations.
- Affected-citizen count.
- Community impact signal:
  - **Local**
  - **Elevated**
  - **Widespread**
- Incident impact is separate from the ML priority prediction.

### Department / Officer
- Department Head dashboard and complaint queue.
- Individual officer accounts and officer-specific work queues.
- Smart officer recommendation with workload/capacity context.
- SLA monitoring and breach visibility.
- Recommended actions, action logging and audit timeline.
- Resolution proof upload.
- Department rerouting/correction.
- Officers only see related complaints that are assigned to them; Department Heads retain full incident oversight.

### Admin
- National overview and complaint monitoring.
- Citizen/officer/department management.
- Add departments and department heads.
- Department and officer workload visibility.
- Audited complaint deletion with a required reason.
- Critical-first priority watch, grouped department maps and role-specific activity feeds.
- Human-reviewed citizen translation feedback that preserves original and processing text.


## Multilingual translation

BHASHINI support is intentionally **on hold pending mentor approval / API onboarding**.

Current prototype translation fallbacks remain available for development/demo use. English complaints skip translation completely.

## Project stack

- **Backend:** FastAPI, SQLAlchemy
- **Database:** PostgreSQL
- **Frontend:** HTML, CSS, JavaScript
- **ML/NLP:** scikit-learn, pandas, NumPy
- **Models:** Logistic Regression selected after multi-model benchmarking
- **Maps / location:** district/state location data and incident locality metadata

## Run locally

```powershell
cd backend
py -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload
```

Serve the `frontend/` directory with Live Server or another local static server (the existing development CORS configuration allows `localhost:5500` and `127.0.0.1:5500`).

Database changes use Alembic. Back up an existing database before its first migration. To enable the Admin login, set `ADMIN_EMAIL` and a bcrypt `ADMIN_PASSWORD_HASH`; generate the hash with `python tools/create_admin_hash.py` from `backend/`. The former shared demo password has been removed.

## Important workflow terminology

A complaint can be **received by a department** before an individual officer is assigned.

- `Received by Department` / `Awaiting Officer` = routed to the responsible department, but no individual officer yet.
- `Officer Assigned` = a named officer owns the case.
- `In Progress` = work has started.
- `Resolved` = department marked the issue resolved; citizen can confirm or reopen.

## Resume-readiness roadmap

### Completed / substantially implemented
- Core grievance workflow
- Role-based Citizen / Officer / Department Head / Admin portals
- Department and priority ML
- Multilingual processing/fallbacks
- Persistent incident clustering
- I'm affected too
- Citizen notifications
- Resolution confirmation/reopen
- Complaint-linked satisfaction rating
- Incident details and community-impact signal
- SLA and audit trail
- Smart officer assignment

### Remaining production work
- Configure managed Redis, production secrets, trusted CORS origins and a production database before deployment.
- Add hosting-specific deployment configuration, monitoring, backups and operational alerts.
- Complete a security review of login throttling, OTP limits, RBAC, file uploads and HTTP security headers.
- Prepare portfolio screenshots, an architecture diagram and a short demo video.

Database schema changes use Alembic; Docker startup applies migrations before serving. A GitHub Actions workflow is included for dependency installation, static checks and existing regression scripts. Configure secrets in the deployment environment; never commit production credentials.

## Model artifacts

Trained models are under `models/`. Benchmark metrics and confusion matrices are under `models/reports/`.

The training data and scripts remain in the project for reproducibility.


## Citizen dashboard workflow cleanup

- The obsolete **Rejected** metric was removed because CivicFlow does not currently expose a department/officer rejection workflow.
- Recent Complaints now includes **View** and **Track** actions.
- Community incident membership checks use the full persisted cluster (including resolved reports), so a citizen who has already filed a report is never asked to click **I'm affected too** for that same incident.


## Citizen information architecture

- **View Complaint** = current/live handling snapshot: responsible department, assigned officer, latest update and next expected action.
- **Track Complaint** = complete lifecycle: Submitted → Received by Department → Individual Officer Assigned → In Progress → Resolved.
- **Incident Details** = community-level summary: total, active and resolved report counts, affected citizens and a small recent-report preview.

Citizen incident pages do not expose another citizen's full complaint details. Department Heads retain full incident oversight. Individual officers only receive related-case context for complaints assigned to them.

## Stabilization and regression

The current build includes a performance and cleanup pass:

- dashboard statistics use aggregate SQL instead of loading entire complaint lists;
- community incidents are batch-loaded instead of issuing several queries per incident card;
- officer accountability data is batch-loaded instead of querying assignments per officer;
- persisted incident backfill has a fast startup check;
- common complaint/user lookup columns have database indexes;
- state/district data is cached for the browser session;
- obsolete manual language-repair endpoints and UI CSS were removed;
- `backend/tools/regression_check.py` exercises Citizen, Department Head, Officer and Admin workflows against an isolated temporary database.



## Email verification and password recovery

CivicFlow uses OTP only where it adds value:

- **First-time citizen registration:** registration details are held temporarily, a 6-digit OTP is sent to the submitted email, and the account is created only after successful verification.
- **Forgot password:** a 6-digit OTP is sent to the registered email before a new password can be set.
- **Normal login:** remains email/username + password. OTP is not required on every login.

OTP controls:
- 5-minute expiry by default
- 60-second resend cooldown
- maximum 5 incorrect attempts
- resending invalidates the previous code
- OTPs are stored as hashes, not plaintext
- duplicate email/phone registration is checked before and again after verification

The current development build keeps short-lived OTP challenges in process memory. For a multi-instance production deployment, move that temporary challenge store to Redis or another shared TTL store.


## Operational maturity features

Three production-oriented workflow features are now included:

- **Escalation hierarchy:** persistent Level 1 (SLA at risk), Level 2 (SLA breached), and Level 3 (critical SLA breach) escalation records. Department Heads get an escalation queue with acknowledgement; Admin gets system-wide oversight and closure.
- **Historical officer performance:** metrics are calculated from stored complaint assignments, resolution timestamps, SLA outcomes, citizen reopen events, and complaint-linked citizen ratings. The dashboard shows resolution rate, SLA compliance, average resolution time, rating, reopen count, and a transparent operational performance index when history exists.
- **Geographic incident hotspots:** Admin receives an OpenStreetMap/Leaflet hotspot view built only from complaints that contain real latitude/longitude values. Nearby complaint coordinates are grouped into small operational cells and summarized by active cases, high/critical cases, and distinct incident clusters.


## Resume-ready product layer

The project now uses one shared `frontend/css/design-system.css` across the complete web interface so Citizen, Department, Officer and Admin experiences follow the same visual language: consistent navigation, surfaces, typography, tables, status chips, forms, spacing, dark mode and responsive behaviour.

The next roadmap items included in this build are:

- **Administrative exports:** authenticated Admin CSV and PDF grievance reports.
- **BHASHINI production integration layer:** server-side NMT configuration, validated translation output, timeout handling, small translation cache and a non-secret readiness indicator in Admin. Live BHASHINI calls activate when approved credentials are placed in the environment.
- **Security hardening:** bounded login failure tracking and temporary lockout, configurable production CORS, common security response headers, upload MIME/type and 15 MB size validation, plus `/health` database readiness.

Existing escalation hierarchy, historical officer performance and coordinate-backed geographic hotspots remain included.


## Landing redesign preservation pass

The public landing page header and hero are redesigned while preserving the complete previous landing experience below them: public live statistics, AI/service cards, command map, department performance, complaint journey, FAQ, user feedback and footer. Dark mode and the original `index.js` interactions/data loading remain active.


## Docker development stack

The project now includes Dockerized frontend/backend, PostgreSQL 16 with persistent storage, and Docker Compose orchestration.

```powershell
Copy-Item .env.docker.example .env.docker
# Set ADMIN_EMAIL and replace ADMIN_PASSWORD_HASH with output from:
#   cd backend; python tools/create_admin_hash.py
docker compose --env-file .env.docker up --build
```

Open `http://localhost:8080`.

The Nginx frontend proxies `/api` to FastAPI, while Live Server on ports 5500/5501 still uses `http://127.0.0.1:8000`.


## Translation provider strategy

For the final academic review, CivicFlow uses a **zero-cost translation chain**:

1. **Google Translate public web endpoint** — primary broad-language, auto-detected translation to English; no API key or billing account is required.
2. **BHASHINI NMT** — Indian-language fallback once the API request is approved.
3. **Offline civic interpretation** — conservative last-resort handling for recognizable civic-domain Odia complaints.
4. Additional public providers remain disabled by default to avoid repeated rate-limit failures.

The free Google path includes request timeout, small retry/backoff, translation caching, output validation, and a short circuit breaker so a temporary provider failure does not repeatedly block grievance submission.

Important limitation: the free Google web endpoint is an unofficial public endpoint and therefore cannot provide a guaranteed production SLA. CivicFlow always preserves the original citizen text and fails safely if translation is unavailable.


## Similarity vs geographic grouping

CivicFlow intentionally separates two different questions:

- **Similar Meaning Complaints (Complaint Details):** compares complaint issue text only. District, area, pincode and GPS do not make two complaints appear semantically similar.
- **Complaints by Location (Department Head Dashboard):** provides a separate geographic workload hierarchy using real stored fields: State → District → Area/Locality (with pincode fallback) → individual complaints.

The application does not call an Area/Locality an official “Block” because the current citizen complaint form does not collect a verified government block field.

Translation provider names are not exposed in the user interface. The backend writes an internal console log such as `[TRANSLATION] ... provider=google-free-web` or `provider=bhashini` for developer/supervisor verification.


## Operational translation coverage

For multilingual citizen submissions, CivicFlow preserves the original text while creating English operational copies for the Department/Officer workflow.

Translated fields:
- complaint title
- complaint description
- area/locality
- address
- landmark

Structured State, District and Pincode values remain standardized and are not machine-translated.

The Department complaint list, complaint details, similar-meaning results and geographic Area/Locality grouping prefer the English operational copy. Existing older multilingual complaints are lazily backfilled when Department staff load them.

Translation provider information is printed only to the backend terminal, for example:

`[TRANSLATION] title | language=te | provider=google-free-web | method=google-free-web | success=True`

It is not exposed to citizens or department users.


## Voice accessibility and Officer Guide

### Voice Complaint
Citizens can speak instead of typing. The browser converts speech to text using Web Speech Recognition, and the resulting local-language text enters CivicFlow's existing multilingual workflow. The original transcript is preserved while English operational copies are created for department routing and staff use.

Voice input can fill:
- complaint description
- title
- area/locality
- landmark
- address

If the citizen speaks the description before entering a title, CivicFlow creates a short title from the first spoken sentence. State and District continue to use structured dropdowns.

CivicFlow itself does not store the microphone audio in this workflow; it stores the resulting text. Browser speech-recognition availability depends on the user's browser and device. Chrome/Edge provide the most reliable support for the prototype.

### Officer Guide
Individual officers receive an in-app workflow assistant that explains assigned-case handling, status updates, SLA deadlines, resolution proof, priority, rerouting, similar complaints, notifications and citizen reopening. The guide is deterministic and project-specific rather than a general-purpose LLM, so it does not require a paid AI API. Officers may type a question or, in supported browsers, ask by voice.


## Voice complaint UX refinement

Voice input is focused on the complaint description, which is the longest and hardest field for low-literacy users to type.

The form uses one shared Complaint Language selector instead of a second voice-language setting. Typed complaints may remain on Auto-detect. Voice recognition uses the selected complaint language when available; otherwise it falls back to the browser locale and CivicFlow infers the written script from the final transcript to update the language hint.

Structured location fields remain manual/current-location based because speech-recognition errors in addresses, locality names and pincodes can reduce routing and geographic-analysis accuracy.

For voice-first users, CivicFlow derives a short title from the first spoken sentence when no title was entered. Users can also listen back to the captured description before submission.


## Final language auto-detect UX

Complaint Language defaults to **Auto-detect**. Manual language selection is hidden behind a small override control and is intended only when detection or browser voice recognition needs help. Voice remains description-first; the transcript is editable and flows through CivicFlow's multilingual translation pipeline.


### Automatic Listen Back voice selection

When Complaint Language remains on Auto-detect, CivicFlow detects the language from the final voice transcript and uses that language only for Listen Back playback. The form itself can remain in Auto-detect mode.

Examples:
- Telugu transcript -> `te-IN`
- Odia transcript -> `or-IN`
- Hindi transcript -> `hi-IN`
- Bengali transcript -> `bn-IN`
- Tamil transcript -> `ta-IN`

CivicFlow also asks the browser speech-synthesis engine for an installed voice whose locale matches the detected language, instead of relying only on the computer's default voice. A citizen can still use Choose manually when script detection is ambiguous, such as Hindi/Marathi/Nepali in Devanagari or Romanized local-language text.


### Voice recording language requirement

CivicFlow keeps Auto-detect for typed complaints, but voice recording requires the citizen to select the spoken Complaint Language before the microphone starts.

This is intentional: browser speech recognition needs the language locale before listening (for example `te-IN` or `or-IN`). Detecting the transcript after recording cannot retroactively improve speech recognition, and it may also cause Listen Back to use the wrong installed voice/accent.

There is still only one language selector in the form. The user does not choose a second voice language.


## Expanded written-language coverage

CivicFlow separates text translation capability from browser voice capability.

- Typed complaints use a broad searchable language selector and can still use Auto-detect.
- Voice input remains restricted to a conservative set of languages with configured browser speech locales in the prototype.
- Selecting a text-supported language that is not voice-enabled disables the microphone and clearly tells the citizen that typed submission is still supported.
- Department/Officer complaint details show the citizen's **Original Language** while the English processing copy remains available separately.

This avoids falsely claiming speech support for languages that the browser may not recognize reliably.


## Sentence-BERT semantic complaint similarity

CivicFlow's **Similar Meaning Complaints** feature now uses **Sentence-BERT embeddings + cosine similarity** rather than hand-written issue rules.

Pipeline:

1. Take the complaint's English processing copy (`translated_text`) when available.
2. Encode it with `sentence-transformers/all-MiniLM-L6-v2`.
3. L2-normalize the embeddings.
4. Encode up to 300 recent complaints from the same department in a batch.
5. Compute cosine similarity using matrix dot product.
6. Keep only matches above `SBERT_SIMILARITY_THRESHOLD` (default `0.64`).
7. Rank matches from highest to lowest semantic similarity.

The Sentence-BERT model is loaded lazily once per backend process and reused. Geography remains excluded from semantic similarity and is handled separately by CivicFlow's geographic grouping feature.

Environment variables:
- `SBERT_MODEL_NAME`
- `SBERT_SIMILARITY_THRESHOLD`

The first run may download the pretrained Sentence-BERT model if it is not already cached.


## SBERT caching and direct-match semantics

Sentence-BERT is preloaded before FastAPI reports the application as ready.

On the first run only, CivicFlow downloads `sentence-transformers/all-MiniLM-L6-v2` and saves a reusable local copy under:

`backend/.model_cache/all-MiniLM-L6-v2`

Future backend starts load this local copy with `local_files_only=True`, so the model is not downloaded again. The local model cache is excluded from Git.

Complaint embeddings are also cached in memory during the backend process so reopening the same complaints does not repeatedly encode the same text.

### Why similar lists may differ

The Department view now labels the section **Direct Semantic Matches**.

Sentence similarity is pairwise and symmetric:

- if Complaint 34 directly matches Complaint 23, Complaint 23 also directly matches Complaint 34;
- however, if 23 also matches 24 and 25, it does **not** mean that 34 must match 24 or 25.

Semantic similarity is not transitive. CivicFlow therefore does not recursively merge direct Sentence-BERT matches into one cluster, which avoids unrelated complaints becoming connected through a weak chain.

The result limit is increased to 50 so a small project dataset is not made asymmetric merely by a low top-N cutoff.


## Explainable semantic matches

Sentence-BERT + cosine similarity remains the only mechanism that decides whether two complaints are semantically similar.

After a match is selected, CivicFlow adds a separate explanation layer that extracts shared content phrases and civic concepts from the two English processing copies. It produces an officer-friendly reason such as:

`Both complaints describe a closely related water supply interruption issue. Shared key concepts include "water supply" and "tap". Semantic similarity: 78%.`

The explanation layer does not alter the SBERT score, threshold, or match decision. It exists only to make semantic matches understandable and auditable for Department Heads and Officers.


## Evidence-based SBERT explanations

The Similar Complaint explanation no longer just repeats generic department words such as `water`, `road` or `electricity`.

After Sentence-BERT decides that two full complaints are similar, CivicFlow performs a second explanation-only SBERT pass over short sentences/clauses from both complaints. It selects the closest pair of reported statements and shows those exact statements to the officer.

Example:

`Why this matches: the closest reported details are “No regular supply is reaching our household taps” and “Residents have not received water from the taps since morning”. Those two statements express a very similar condition (84% evidence similarity). Overall complaint similarity: 78%.`

Generic civic nouns are excluded from the optional shared-term explanation so that the reason focuses on the actual reported condition rather than merely repeating the department topic.

The explanation pass never changes the match threshold or score.


## Responsive UI

CivicFlow includes a shared mobile/tablet responsive layer loaded after each page's existing stylesheet. It standardizes viewport behavior, collapses dashboards and form grids, prevents horizontal page overflow, makes tables horizontally scrollable, adapts cards/forms/modals, and converts the Officer Guide into a phone-friendly floating panel.

Target breakpoints:
- Desktop: above 1024px
- Tablet: 769–1024px
- Mobile: up to 768px
- Small phones: up to 480px


## Performance architecture

CivicFlow keeps page navigation independent from expensive AI/network work.

- Department complaint details render from a fast core endpoint.
- Sentence-BERT similar-complaint analysis is fetched asynchronously after the page is visible.
- Sentence-BERT candidate embeddings are batch-encoded and cached in memory.
- The pretrained model remains cached locally under `backend/.model_cache/`.
- Dashboard/list/location GET endpoints do not call external translation providers.
- English translation is generated during complaint ingestion and reused from the database.
- Officer assignment recommendations load without blocking the complaint's first render.

This prevents AI inference or translation-provider latency from making normal navigation feel frozen.


## Administrative location data

The citizen location form is deliberately independent from the ML training datasets.

- State/district suggestions come from a dedicated administrative JSON file.
- District is an editable autocomplete field, so a newly created or missing district can still be entered even if the bundled JSON is stale.
- Odisha has all 30 districts in the bundled list, including Rayagada.
- Browser GPS remains the preferred exact complaint location.
- If GPS is unavailable, the backend first uses the bundled district-coordinate dataset.
- If a district has no bundled coordinate, CivicFlow performs a one-time OpenStreetMap/Nominatim district lookup and stores the approximate district centre in `dataset/district_coordinate_cache.json`.
- Cached district coordinates are reused on later submissions.
- If geocoding fails, CivicFlow stores no fake `0,0` coordinate.
- District-centre coordinates are only approximate map fallbacks and are never treated as exact citizen GPS positions.

Administrative dropdown data should be refreshed periodically from an official government directory such as India's Local Government Directory / Integrated Government Online Directory rather than from complaint or ML datasets.

## All-India administrative location coverage

The State/District selector is maintained as administrative reference data and is independent of CivicFlow's ML training datasets.

- All 28 states and 8 Union Territories are present.
- District suggestions are no longer capped/truncated to a fixed number such as 25.
- Current project coverage includes recent changes such as Hansi (Haryana), Kushavati (Goa), Vav-Tharad (Gujarat), Meluri (Nagaland), and the Andhra Pradesh reorganisation including Markapuram and Polavaram.
- District remains an editable autocomplete field, so citizens are not blocked if an administrative boundary changes before the bundled reference file is refreshed.
- Browser GPS remains the preferred exact complaint coordinate.
- Missing district-centroid coordinates use the one-time geocoding + persistent cache fallback; CivicFlow does not store fake `0,0` coordinates.
- `backend/tools/validate_location_data.py` detects truncated state lists, missing jurisdictions, duplicate district names, and blank values.

The bundled administrative reference should be periodically refreshed from Government of India LGD/IGOD and current State/UT notifications.


## Latest updates
The admin Hotspots page includes an explainable 24-hour incident-burst queue. Admin and Department Head map analysis updates with the current state, district and area filters. Local previews on any localhost port route API calls to the backend. Address lookup remains a suggested point that citizens review and confirm before submission. Citizens can report translation concerns for human review; original and processing text remain unchanged. See `docs/EMERGING_INCIDENT_ALERTS.md`.

### Updating an existing database

If the Department Head complaint detail page returns a server error mentioning a missing `translation_feedback` column, stop the backend, activate the project's backend virtual environment, and run `alembic -c alembic.ini upgrade head` from `backend/`. This applies the schema repair migration before restarting the API. Back up the database first; do not manually drop the feedback table.
