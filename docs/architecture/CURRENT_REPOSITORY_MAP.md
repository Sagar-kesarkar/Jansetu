# JanSetu (जनसेतु) — Current Repository Architecture Map

This document details the architectural layout, active component paths, channel routers, and database models of the **JanSetu** platform.

---

## 🏛 Active Component Paths

| Component | Active Filepath | Port / Entrypoint | Technology Stack |
|---|---|---|---|
| **Backend API** | `backend/` | `http://localhost:8080` (`app.main:app`) | FastAPI, SQLAlchemy 2.0, Pydantic v2, Google GenAI SDK |
| **Citizen Web Portal** | `frontend/` | `http://localhost:5173` | React 19, Vite, Leaflet, Recharts |
| **Officials Console** | `frontend-admin/` | `http://localhost:5174` | React 19, Vite, Recharts, Lucide Icons |
| **Channel Telephony** | `backend/app/channels/` | Webhook & CLI (`python -m app.channels.simulator`) | IVR (Exotel), SMS (DLT/Exotel), WhatsApp Cloud API |
| **Database & Models** | `backend/app/db/` | `backend/jansetu.db` | SQLite (Development) / PostgreSQL (Production) via SQLAlchemy |
| **Data Reference & Scripts** | `data/` | `data/reference/`, `data/scripts/` | LGD codes, geographic aliases, synthetic requests, IVR audio prompts |
| **Archived Artifacts** | `_archive_unwanted_files/` | Inactive | Preserved legacy frontend and migration kit prompts |

---

## 📁 Repository Directory Structure

```text
JanSetu/
├── .github/
│   └── workflows/
│       └── ci.yml                      # Automated CI workflow for tests and builds
├── _archive_unwanted_files/
│   ├── ARCHIVE_MANIFEST.md             # Inventory of archived files and restoration steps
│   ├── docs/                           # Archived implementation prompts
│   └── legacy-frontend-admin/          # Archived legacy admin console
├── backend/
│   ├── alembic/                        # Database migration environment
│   │   └── versions/
│   ├── app/
│   │   ├── analytics/                  # District scoring and policy prioritization
│   │   ├── channels/                   # WhatsApp, SMS, IVR state machines & prompts
│   │   ├── db/                         # SQLAlchemy models, seed scripts & session
│   │   ├── i18n/                       # Multilingual keyword indices & translations
│   │   ├── models/                     # Pydantic schemas & taxonomy definitions
│   │   ├── routers/                    # FastAPI endpoints (intake, track, official, funds, etc.)
│   │   ├── services/                   # Gemini model pool, geocoding, privacy, evidence
│   │   │   └── financial_sources/      # Government budget adapters & sync engine
│   │   ├── config.py                   # Pydantic Settings & environment loader
│   │   └── main.py                     # FastAPI application factory and lifespan
│   ├── tests/                          # 280-test Pytest suite
│   ├── Dockerfile                      # Container definition for backend API
│   ├── alembic.ini                     # Alembic configuration
│   └── requirements.txt                # Python dependencies
├── data/
│   ├── evidence/                       # Privacy-sanitized complaint media attachments
│   ├── ivr_prompts/                    # Pre-recorded audio prompts across 13 Indian languages
│   ├── raw/                            # Ingestion cache for raw government data
│   ├── reference/                      # 72 districts, 542 place aliases, infra indices
│   ├── scripts/                        # Reference generation & seed data builders
│   └── synthetic/                      # Representative multilingual citizen complaints
├── docs/
│   ├── api/                            # REST API reference documentation
│   ├── architecture/                   # System architecture and repository maps
│   ├── data-sources/                   # Government budget sources, provenance & audit
│   ├── deployment/                     # Deployment instructions for Cloud / Containers
│   └── submission/                     # Demo script, pitch deck, compliance checklist
├── frontend/                           # Citizen Web Application (React 19 + Vite)
├── frontend-admin/                     # Officials Console (React 19 + Vite)
├── infra/                              # Deployment scripts and container orchestration
├── .env.example                        # Safe environment variable template
├── .gitignore                          # Git ignore rules for secrets, PII, and build artifacts
├── CONTRIBUTING.md                     # Contribution guidelines
├── EVENT_COMPLIANCE_REPORT.md          # Comprehensive event audit & evidence report
├── LICENSE                             # MIT License
├── Makefile                            # Developer task automation
├── README.md                           # Master project documentation
├── REPOSITORY_ORGANIZATION_REPORT.md   # Organization before/after inventory
├── RUN.md                              # Step-by-step local execution guide
└── SECURITY.md                         # Security policy, PII protection & reporting
```

---

## 🔄 Verified Active Application Flows

1. **Citizen Intake & Tracking**:
   - Web (`/intake/report`, `/intake/text`, `/intake/voice`)
   - WhatsApp Cloud API webhook (`/channels/whatsapp/webhook`)
   - SMS webhook (`/sms/incoming`)
   - IVR Call Handling (`/channels/ivr/event`)
   - Citizen Token Lookup (`/track/{token}`)
2. **Officials Casework & Reply**:
   - Zero-PII Docket Queue (`/official/requests`)
   - Official Responses & Stage Progression (`/requests/{id}/responses`)
   - Real-time Events Stream (`/official/events/stream`)
3. **Public Funds Transparency**:
   - Multi-tier financial summaries (`/api/v1/funds/overview`)
   - District & Sector allocations (`/api/v1/funds/districts`, `/api/v1/funds/sectors`)
   - Verified data sources catalog (`/api/v1/funds/sources`)
