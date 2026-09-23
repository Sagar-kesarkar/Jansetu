# JanSetu (जनसेतु) — REST API Reference

The JanSetu platform exposes a RESTful API with automated OpenAPI specifications accessible at `/docs` or `/openapi.json`.

---

## 🧭 Endpoint Catalog

### 1. Citizen Ingestion & Reporting
- `POST /intake/report`: Multipart intake supporting combined text, audio voice note, and photograph attachment.
- `POST /intake/text`: JSON citizen complaint filing (`text`, `language`, `channel`, `location_text`).
- `POST /intake/voice`: Voice note intake with automatic transcription and structuring.

### 2. Citizen Request Tracking
- `GET /track/{token}`: Accountless tracking endpoint returning step progression, official replies, translated notes, and history timeline.
- `GET /requests/{id}/evidence/photo`: Retrieve sanitized case photograph attachment.

### 3. Officials Console & Casework Desk
- `GET /official/requests`: Filterable docket list for government officers (Zero-PII).
- `GET /official/dashboard/summary`: Aggregate metrics across categories, channels, urgency, and statuses.
- `GET /official/events/stream`: Server-Sent Events (SSE) live feed of incoming complaints.
- `POST /requests/{id}/responses`: Add official reply, trigger Gemini translation, and advance case status.
- `PATCH /requests/{id}/status`: Update case status (`UNDER_REVIEW`, `IN_PROGRESS`, `RESOLVED`, etc.).

### 4. Authoritative Public Funds
- `GET /api/v1/funds/overview`: High-level 4-KPI budget metrics (Allocated, Released, Spent, Available).
- `GET /api/v1/funds/districts`: Comparative district financial breakdown and grievance pressure.
- `GET /api/v1/funds/sectors`: Sector-level budget distribution and utilization signals.
- `GET /api/v1/funds/sources`: Catalog of official government data sources, URLs, and sync timestamps.
- `GET /api/v1/funds/coverage`: State and district financial data availability map.

### 5. Analytics & Prioritization
- `GET /hotspots`: Identify geographic grievance clusters ranked by urgency and volume.
- `GET /recommendations`: Ranked infrastructure project interventions with explainable evidence metrics.
- `GET /districts`: Directory of covered districts, LGD codes, demographics, and baseline indices.

### 6. Channels & Telephony
- `POST /channels/whatsapp/webhook`: Inbound WhatsApp Cloud API webhook receiver.
- `POST /sms/incoming`: Inbound SMS webhook receiver (DLT compliant).
- `POST /channels/ivr/event`: IVR state machine call handler for inbound voice telephony.
- `POST /channels/ivr/hangup`: IVR call termination and cleanup.

### 7. Metadata & Health
- `GET /health`: Service health check (`{"status": "ok"}`).
- `GET /capabilities`: Configured taxonomy, languages, model status, and scoring parameters.
