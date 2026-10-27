CivicFlow AI — SLA and AI Summary Fix v2

Apply this ZIP carefully:
1. Extract to a separate folder.
2. Back up the corresponding files in your existing D:\CivicFlow-AI project.
3. Copy these files from the extracted project into the same relative paths in D:\CivicFlow-AI (preserve folders):
   - backend\app\main.py
   - backend\app\services\ai_service.py
   - backend\app\routes\complaint_routes.py
   - frontend\department_complaint_details.html
   - frontend\js\department_details.js
4. Do not replace or modify any .env files. Keep your existing database and local configuration.
5. Restart from PowerShell:
   cd D:\CivicFlow-AI\backend
   $env:FRONTEND_DIR = "D:\CivicFlow-AI\frontend"
   uvicorn app.main:app --reload
6. Open the department complaint details page in Edge and press Ctrl+F5.

Changes: removes the redundant Target field from the SLA UI, labels the Department Head assignment deadline and countdown explicitly, fixes a stale JavaScript reference to the removed Target field, displays the current API summary field, and retains the frontend static mount and same-origin microphone Permissions-Policy fix.

Note: this is a targeted patch ZIP; copy only the five listed files into your existing project. Do not overwrite your entire project or .env files.
