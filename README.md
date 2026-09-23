# JanSetu — AI for Digital Public Infrastructure and Governance

> **JanSetu (जनसेतु)** is an AI-powered Digital Public Infrastructure (DPI) platform enabling 1.4B Indian citizens to report civic grievances across 13 Indian languages via voice notes, WhatsApp, SMS, and IVR telephony. Powered by **Google Gemini**, JanSetu automatically transcribes native speech, extracts urgency, validates locations, and issues high-entropy tracking tokens for real-time progress monitoring, integrated with an authoritative Public Funds transparency portal and an official casework desk.

---

## 🧭 Problem Statement & Communities Served

Over 600 million Indian citizens face language, literacy, and digital barriers when attempting to file civic complaints (such as broken roads, dry water pipes, or power outages). Existing portals require typing in formal English, navigating complex menus, and providing private phone numbers or OTPs.

JanSetu eliminates these friction points by providing:
- **Linguistic Inclusion**: Dialect-tolerant voice notes and messaging across 13 Indian languages.
- **Accountless Access**: Secure tracking via high-entropy tokens (`JS-XXXX-XXXX`) without passwords or OTPs.
- **Civic Accountability**: Direct correlation between citizen grievances and authoritative government budget allocations.

---

## 🌟 Key Features

1. **Omnichannel Citizen Intake**: Voice notes and text via Web, conversational WhatsApp, DLT-compliant SMS, and interactive IVR telephony.
2. **Google Gemini Multimodal AI**: Real-time audio transcription, sector classification, urgency extraction, and compound complaint splitting.
3. **Mandatory Location Gating**: Validation against 72 LGD districts and 542 geographic aliases.
4. **Officials Casework Console**: Zero-PII docket queue with real-time SSE live event streaming and automated multilingual reply translation.
5. **Authoritative Public Funds Transparency**: Multi-tier budget tracking with strict accounting precedence (RE > BE, Actual > Payment) preventing double-counting.
6. **Explainable Priority Scoring**: Deterministic, un-biased formula balancing citizen demand, demographic deprivation, and infrastructure gaps.

---

## 🏛 System Architecture & Workflow

```
[Citizen Voice / Text / WhatsApp / IVR]
                 │
                 ▼
     [FastAPI Ingest Pipeline]
                 │
                 ├──► [Privacy Sanitizer: HMAC-SHA256 Pseudonymization]
                 ├──► [Google Gemini: Transcription & Entity Structuring]
                 └──► [Location Gating: LGD Directory Resolution]
                 │
                 ▼
     [Unique Token Issued: JS-XXXX-XXXX]
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
[Officials Console]   [Citizen Tracking]
(Casework & Reply)    (Real-time Timeline)
```

---

## 🤖 Google Gemini AI Integration & 7-Tier Model Pool

To guarantee 100% platform availability on Google AI Studio free-tier quotas (20 requests/day/model), JanSetu implements an automatic 7-tier model pool (`backend/app/services/model_pool.py`):
1. `gemini-3.5-flash` (Primary)
2. `gemini-3.6-flash`
3. `gemini-3.7-flash`
4. `gemini-3-flash-preview`
5. `gemini-2.5-flash`
6. `gemini-3.5-flash-lite`
7. `gemini-3.1-flash-lite`

If all models or network connectivity are offline, JanSetu gracefully degrades to deterministic keyword tokenization without dropping citizen requests.

---

## 📞 Multilingual Channels & Voice Telephony

| Channel | Input Method | Capabilities | Language Support |
|---|---|---|---|
| **Citizen Web Portal** | Audio & Text | Live microphone recording, photo attachment, real-time ticket receipt | 13 Indian Languages + English |
| **WhatsApp Chatbot** | Conversational Text/Media | Interactive guidance, location resolution, token confirmation | 13 Indian Languages + English |
| **SMS Gateway** | Text / Feature Phone | DLT template compliant, concise status updates | 13 Indian Languages + English |
| **IVR Voice Telephony** | Voice & DTMF Keypad | Multi-language voice prompts, automated speech recording | 13 Indian Languages + English |

---

## 📊 Public Funds Transparency Engine

JanSetu integrates official government budget data sources:
- **Maharashtra State Finance**: District and sector-level budget line items.
- **Open Government Data (OGD) India**: Central and state outlays.
- **eGramSwaraj**: Panchayati Raj rural infrastructure allocations.

### Accounting Precedence Rules:
- **Allocations**: Revised Estimates (`RE`) supersede Budget Estimates (`BE`). No double-counting (`RE + BE` is strictly prohibited).
- **Expenditures**: Audited Actuals (`ACTUAL`) supersede provisional payments (`PAYMENT`).
- **Releases**: Tracked as an independent intermediate treasury stage.

---

## 🗂 Repository Structure

```text
JanSetu/
├── .github/workflows/ci.yml       # GitHub Actions CI workflow
├── _archive_unwanted_files/       # Historical prompts and legacy console archive
├── backend/                       # FastAPI backend, routers, services, tests
│   ├── app/                       # Core API application code
│   └── tests/                     # 280-test Pytest suite
├── data/                          # LGD reference datasets, aliases, and IVR prompts
├── docs/                          # Architecture, API, Data Sources, and Submission docs
│   ├── api/                       # REST API reference documentation
│   ├── architecture/              # System design and repository maps
│   ├── data-sources/              # Financial data provenance audit
│   ├── deployment/                # Production container deployment guide
│   └── submission/                # Demo script, pitch deck, publishing guide
├── frontend/                      # Citizen Web Application (React 19 + Vite)
├── frontend-admin/                # Officials Console (React 19 + Vite)
├── infra/                         # Deployment scripts and container configs
├── .env.example                   # Environment configuration template
├── .gitignore                     # Git tracking exclusions
├── CONTRIBUTING.md                # Contribution guidelines
├── LICENSE                        # MIT License
├── README.md                      # Master project README
├── RUN.md                         # Detailed step-by-step local execution guide
└── SECURITY.md                    # Security policy & privacy guarantees
```

---

## 🛠 Local Setup & Installation

### 1. Prerequisites
- Python 3.12+
- Node.js 20+ and npm
- Free Gemini API Key from [Google AI Studio](https://aistudio.google.com/apikey)

### 2. Environment Configuration
```bash
cp .env.example .env
# Edit .env and insert your GEMINI_API_KEY
```

### 3. Backend Setup
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate  # Linux/macOS

cd backend
pip install -r requirements.txt
python -m app.db.seed        # Seed districts, indices, and reference data
uvicorn app.main:app --port 8080 --reload
```

### 4. Citizen Frontend Setup
```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

### 5. Officials Console Setup
```bash
cd frontend-admin
npm install
npm run dev                  # http://localhost:5174
```

---

## 🧪 Testing & Verification

Run the comprehensive test suite and production builds:

```bash
# Run backend pytest suite (280 passing tests)
cd backend
pytest -v

# Run Citizen Frontend build
cd ../frontend
npm run build

# Run Officials Console build
cd ../frontend-admin
npm run build
```

---

## 🔒 Privacy & Security Guarantees

- **Zero PII**: Citizen phone numbers are converted to HMAC-SHA256 hashes (`anon_...`) and never saved in raw text.
- **Protected Officials Desk**: Officers only see scrubbed locality and ward-level details.
- **Accountless High Entropy**: $30^8$ non-sequential token space protects citizen tracking against enumeration attacks.

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
