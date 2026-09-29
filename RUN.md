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

For an isolated feature preview, run `python preview_submissions.py` from
`backend/` using the project virtual environment. This uses ignored
`backend/.local-preview/` storage, creates its own stable secret, loads reference
districts and disables Gemini. It never opens the normal complaint database.
The preview is intentionally synthetic, not a seeded full financial demo.

For ordinary backend startup, also configure `SUBMISSION_SECRET` with a private
random value of at least 32 characters. Keep it stable. The anonymous session
endpoint fails closed if it is missing. Configure HTTPS secure cookies for hosting.

In a separate terminal from the repository root:

```sh
cd frontend-citizen
npm ci
npm run dev
```

Open http://localhost:5173. The folder was renamed from frontend-citizen/ to frontend-citizen/; the root run_frontend.bat launcher remains supported.

In development, citizen API calls default to `/api`, proxied by Vite to
`http://127.0.0.1:8080`, so required cookies are first-party. An explicit
`VITE_API_BASE` still overrides this. Accept the cookie choice before submitting;
change it later through Cookie settings in the footer.

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
npm test
npm run build
# frontend-admin/
npm run build
```

Mock external services in automated tests. Build success does not prove backend tests or provider delivery. The citizen frontend has Node tests (`npm test`); the admin frontend has no separate test script.

For a manual demonstration, file a synthetic report, copy its token, update it in the console and track it on the citizen website. Website channel simulation does not count as live messaging or telephony verification. Never use real citizen data for this demo.
