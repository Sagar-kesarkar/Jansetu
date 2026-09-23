# Local development

## Requirements

Use Python 3.12 and Node.js 22.12 or later in the Node 22 release line, with npm and Git. A Gemini key is optional. No billing account is required for local fallback mode.

```sh
git clone https://github.com/Sagar-kesarkar/Jansetu.git
cd Jansetu
python -m venv .venv
```

Activate with `.venv\\Scripts\\Activate.ps1` in PowerShell or `source .venv/bin/activate` on Linux/macOS.

## Backend

From the repository root, with the virtual environment active:

```sh
cd backend
python -m pip install -r requirements.txt
python -m app.db.seed
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

The seed command creates tables and loads available reference/demo records. Inspect its output for actual counts. Open http://localhost:8080/docs for API documentation and /health for health status.

For optional configuration, copy the root .env.example to backend/.env. The current settings loader resolves its REPO_ROOT to backend/, so a root-only .env is not reliably loaded. Alternatively use process environment variables. Leave GEMINI_API_KEY empty for fallback mode; template placeholders are not credentials.

Set CITIZEN_REF_SALT to a private, stable value for channel sessions that must survive restarts. CORS_ORIGINS must contain both frontend origins. Relative SQLite paths resolve from the process working directory; consistently start the API from backend/.

## Citizen website

In a separate terminal from the repository root:

```sh
cd frontend-citizen
npm ci
npm run dev
```

Open http://localhost:5173. The folder was renamed from frontend-citizen/ to frontend-citizen/; the root run_frontend.bat launcher remains supported.

## Officials console

In another terminal from the repository root:

```sh
cd frontend-admin
npm ci
npm run dev
```

Open http://localhost:5174 and use the displayed demo autofill. This is not secure authentication. Both clients default to http://localhost:8080; VITE_API_BASE overrides that URL at build time.

## Validation

After finishing related changes, run from the indicated directories:

```sh
# backend/
python -m pytest
# frontend-citizen/
npm run build
# frontend-admin/
npm run build
```

Mock external services in automated tests. Build success does not prove backend tests or provider delivery. Neither frontend currently declares a separate test script.

For a manual demonstration, file a synthetic report, copy its token, update it in the console and track it on the citizen website. Website channel simulation does not count as live messaging or telephony verification. Never use real citizen data for this demo.
