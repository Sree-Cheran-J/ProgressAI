# ProgressAI — FastAPI + MongoDB + ML MVP

This package preserves the supplied HTML/CSS visual design and replaces demo `localStorage` behavior with API calls. It is a college-project MVP, not a production-certified employee surveillance or HR decision system.

## Requirements
- Python 3.11 (64-bit recommended)
- MongoDB Atlas URI or local MongoDB
- Windows PowerShell

## Setup (PowerShell)
```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
Paste the generated value into `.env` as `SECRET_KEY=...`. Set `MONGODB_URI` to your Atlas connection string (replace password, URL-encode special characters, allow your IP in Atlas Network Access) or use local MongoDB. Do not commit `.env`.

Train a synthetic demonstration pipeline (optional; labels and metrics are synthetic):
```powershell
python -m ml.train --rows 1200
```
Run backend:
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000/docs`. Health check: `http://127.0.0.1:8000/health`.

Run frontend in a second PowerShell window:
```powershell
cd ProgressAIrontend
py -m http.server 5500 --bind 127.0.0.1
```
Open `http://127.0.0.1:5500`. Do not open `index.html` through `file://`. If serving from another origin, add it to `FRONTEND_ORIGINS` and restart the API.

## Manager account
Register normally; public registration always creates an employee. Promote one account deliberately from the backend folder after registration:
```powershell
python -m scripts.promote_manager your-manager-email@example.com
```
Restart/log in again to obtain a JWT with manager role. This is an administrative CLI action; do not expose a public role-changing endpoint.

## Test
```powershell
pytest -q
```
The included tests cover ML baseline behavior. For API integration tests, use a dedicated test database and add fixtures for a disposable MongoDB instance before running tests against it; never point destructive tests at production data.

## SMTP reminders
Set `ENABLE_SCHEDULER=true` and provide `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM_EMAIL`. The in-process APScheduler is for single-process local demos only. With multiple workers/replicas use a dedicated scheduler worker/queue and distributed deduplication. Notifications are stored in MongoDB even when SMTP is not configured; emails are skipped if credentials are absent.

## API basics
- `POST /api/auth/register` — full_name, email, password (8+ chars), focus_goal optional.
- `POST /api/auth/login` — email/password; returns bearer access token.
- `GET /api/auth/me`, `GET/PATCH /api/users/me`.
- `GET/POST /api/tasks`, `GET/PATCH/DELETE /api/tasks/{id}`, `PATCH /api/tasks/{id}/status`.
- `POST /api/manager/tasks`, `GET /api/users`, `GET /api/analytics/employee-performance` — manager-only.
- `GET /api/dashboard/summary`, `GET /api/analytics/weekly`, `POST /api/predictions/estimate`, `GET /api/notifications`, `PATCH /api/notifications/{id}/read`.

## Important implementation notes
- JWT is stored in `sessionStorage` by the included browser code: this is convenient for a college demo but accessible to JavaScript and therefore exposed by XSS. Production should prefer Secure, HttpOnly, SameSite cookies plus CSRF protection, strict CSP, TLS, rate limiting, secret rotation, backups, audit review, and security testing.
- User isolation is enforced for employee tasks and notifications. Managers can see all employees/tasks in this single-workspace demo; multi-company use requires `tenant_id`/team membership fields and tenant filters on every query.
- Duration features are known at prediction time. Actual duration is only used as a training target/history for other tasks, never as the same task's inference feature. Historical task duration is currently wall-clock elapsed time, not tracked active work time; add explicit start/pause time logs if active effort is required.
- Synthetic model metrics only validate code paths. Do not use them to evaluate actual employee performance. Collect consented, relevant task outcomes and validate with time-based holdout before relying on predictions.
- Risk classifier is trained from synthetic risk labels for demonstration. If no model file is present, the risk output is explicitly a baseline heuristic. No calibrated uncertainty interval is claimed.
- Five algorithms in the trained bundle: Linear Regression, Random Forest regression, Random Forest classification, Decision Tree classification, K-Means clustering, and KNN recommendation (six model instances, five algorithm families). The current dashboard exposes duration/risk/recommendation outputs; clustering is retained as an analytical artifact for future behaviour grouping and is not a visible feature yet.

### Optional API integration test
Use a disposable MongoDB database (for example set `MONGODB_DATABASE=progressai_test` in `.env`) and then run:
```powershell
$env:RUN_API_INTEGRATION="1"
pytest -q
Remove-Item Env:RUN_API_INTEGRATION
```
The integration test creates a uniquely named test account and task, updates it, and deletes the task. It does not delete the account. Never run this against production data. For a fully isolated CI setup, provision a temporary MongoDB service and inject its URI/database into the test job.
