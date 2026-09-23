# JanSetu (जनसेतु) — Execution & Startup Guide

This document provides step-by-step instructions for installing dependencies, seeding the database, starting all services, and verifying the end-to-end system.

---

## 🧭 Architecture & Port Allocation

| Component | Technology | Default URL / Port | Description |
|---|---|---|---|
| **Backend API** | FastAPI (Python 3.12+) | `http://localhost:8080` (Docs: `/docs`) | Multilingual intake, Gemini structuring, scoring engine, privacy sanitization, and REST API |
| **Citizen Web App** | React 19 + Vite | `http://localhost:5173` | Citizen intake portal (voice/text across 13 Indian languages), tracking token lookup |
| **Officials Console** | React 19 + Vite | `http://localhost:5174` | Casework desk, status management, official reply drafting, priority ranking map |
| **IVR Simulator** | Python CLI | Terminal session | Interactive telephony simulator for voice & DTMF intake in Indian languages |

---

## ⚡ Option 1: 1-Click Startup (Windows Batch Files)

For quick local development on Windows, convenient batch scripts are provided in the repository root:

1. **Start Backend API (`:8080`)**:
   ```cmd
   run_backend.bat
   ```
2. **Start Citizen Web App (`:5173`)**:
   ```cmd
   run_frontend.bat
   ```
3. **Start Officials Console (`:5174`)**:
   ```cmd
   run_admin.bat
   ```
4. **Launch IVR Telephony Simulator**:
   ```cmd
   run_ivr_simulator.bat
   ```
5. **Run Test Suite**:
   ```cmd
   run_tests.bat
   ```

---

## 🛠 Option 2: Manual Step-by-Step Startup

### 1. Prerequisites
- **Python 3.12+** installed and available in PATH.
- **Node.js 18+** and **npm** installed.
- *(Optional but recommended)* Free **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/apikey).

---

### 2. Environment Configuration

Copy the example environment configuration file to `.env`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

Open `.env` and configure your `GEMINI_API_KEY`:
```ini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./jansetu.db
CORS_ORIGINS=http://localhost:5173,http://localhost:5174
```

> **Note:** The platform includes graceful fallbacks and offline heuristics if no Gemini key is provided, but a free key enables full live multilingual audio transcription and entity structuring.

---

### 3. Install Dependencies

#### A. Backend (Python Virtual Environment)
```bash
# Create virtual environment if not already present
python -m venv .venv

# Activate virtual environment:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (CMD):
.venv\Scripts\activate.bat
# Linux / macOS:
source .venv/bin/activate

# Install requirements
cd backend
pip install -r requirements.txt
```

#### B. Citizen Frontend
```bash
cd ../frontend
npm install
```

#### C. Officials Console Frontend
```bash
cd ../frontend-admin
npm install
```

---

### 4. Seed the Database

Populate the database with 72 districts, 542 geographic aliases, 720 infrastructure indices, 720 investment plans, 600 citizen requests, and 498 official replies:

**From repository root:**
```bash
cd backend
python -m app.db.seed
```
*Output confirmation:* `seed complete`

---

### 5. Start Services

Open separate terminal windows/tabs for each service:

#### Terminal 1 — Backend API (FastAPI)
```bash
cd backend
uvicorn app.main:app --reload --port 8080
```
- API Base: `http://localhost:8080`
- Interactive OpenAPI / Swagger Documentation: `http://localhost:8080/docs`
- Health Check: `http://localhost:8080/health`

#### Terminal 2 — Citizen Web App
```bash
cd frontend
npm run dev
```
- Available at: `http://localhost:5173`

#### Terminal 3 — Officials Console
```bash
cd frontend-admin
npm run dev
```
- Available at: `http://localhost:5174`

#### Terminal 4 — (Optional) IVR Telephony Simulator
```bash
cd backend
python -m app.channels.simulator
```
- Follow the interactive terminal prompts to simulate inbound citizen calls, language selection, speech recording, and ticket generation.

---

## 🧪 Verification & Health Checks

### 1. Automated Test Suite
Run the comprehensive 224-test pytest suite:
```bash
cd backend
pytest -v
```
All unit, integration, privacy sanitization, and priority scoring tests should pass (`224 passed`).

### 2. Verify API Endpoints
- **Health Check**:
  ```bash
  curl http://localhost:8080/health
  # Expected: {"status":"ok"}
  ```
- **System Capabilities**:
  ```bash
  curl http://localhost:8080/capabilities
  ```
- **Aggregate Statistics**:
  ```bash
  curl http://localhost:8080/requests/stats
  ```

### 3. End-to-End User Flow Verification
1. Open the **Citizen Web App** at `http://localhost:5173`.
2. Submit a report (via text or simulated voice) in any supported language (e.g., Hindi, Tamil, Bengali, English).
3. Copy the returned tracking token (e.g. `JS-XXXX-XXXX`).
4. Switch to the **Officials Console** at `http://localhost:5174`.
5. Check the incoming casework queue to see the structured complaint, extracted urgency, district mapping, and privacy-scrubbed details.
6. Post an official response or update status in the Officials Console.
7. Return to the Citizen Web App, go to **Track Request**, enter the tracking token, and verify the updated status and official response.

---

## 🔍 Troubleshooting & Common Issues

| Issue | Cause | Resolution |
|---|---|---|
| `Port 8080 / 5173 / 5174 in use` | Another process is holding the port. | Check with `netstat -ano \| findstr "8080 5173 5174"` and terminate conflicting processes. |
| `ImportError: cannot import name 'budget'` | Legacy import in `app/main.py`. | Ensure `app/main.py` is clean and up to date. |
| `CORS Error in Browser` | Frontend port mismatch. | Verify `CORS_ORIGINS` in `.env` contains `http://localhost:5173,http://localhost:5174`. |
| `Vite Network Warning` | Vite bound only to local loopback. | Use `npm run dev -- --host` if exposing over a local network. |
