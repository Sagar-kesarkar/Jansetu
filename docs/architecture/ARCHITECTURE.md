# JanSetu (जनसेतु) — Architecture & System Design

**JanSetu** is an AI-powered Digital Public Infrastructure (DPI) platform designed for equitable grievance redressal, multi-channel citizen intake, and authoritative public funds transparency across India.

---

## 🏛 System Architecture Overview

```
                          ┌────────────────────────────────────────────────────────┐
                          │                    CITIZEN CHANNELS                    │
                          │   Web (Voice/Text) │ WhatsApp │ SMS (DLT) │ IVR Phone  │
                          └───────────────────┬────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FASTAPI INGESTION & PIPELINE                                  │
│                                                                                               │
│  ┌───────────────────────┐   ┌───────────────────────────┐   ┌─────────────────────────────┐  │
│  │   Privacy Sanitizer   │   │     Gemini Model Pool     │   │      Location Resolver      │  │
│  │ HMAC-SHA256 Pseudonym │   │  7-Tier Quota Escalation  │   │  LGD & 542 Alias Directory  │  │
│  │  Zero Phone / Raw PII │   │  Multi-Issue Segmentation │   │ Mandatory Location Gating   │  │
│  └───────────────────────┘   └───────────────────────────┘   └─────────────────────────────┘  │
└─────────────────────────────────────────────┬─────────────────────────────────────────────────┘
                                              │
                                              ▼
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     CORE PERSISTENCE LAYER                                    │
│                                                                                               │
│  ┌───────────────────────────┐    ┌───────────────────────────┐    ┌───────────────────────┐  │
│  │ Citizen Requests (Tokens) │    │  Casework Audit & Replies │    │  Public Funds Tables  │  │
│  │  Entropy: JS-XXXX-XXXX    │    │  Multilingual Body Native │    │ BE / RE / Exp / Alloc │  │
│  └───────────────────────────┘    └───────────────────────────┘    └───────────────────────┘  │
└──────────────────────┬──────────────────────────────────────────────────────┬─────────────────┘
                       │                                                      │
                       ▼                                                      ▼
┌──────────────────────────────────────────────┐       ┌────────────────────────────────────────┐
│             CITIZEN WEB PORTAL               │       │           OFFICIALS CONSOLE            │
│       React 19 + Vite (Port :5173)           │       │      React 19 + Vite (Port :5174)      │
│  - Multilingual Voice/Text Reporting         │       │  - Zero-PII Docket & Casework Desk     │
│  - Real-Time Progress & Timeline Lookup      │       │  - Live SSE Event Streaming            │
│  - Public Funds Citizen Transparency Portal  │       │  - Official Replies & Stage Updates    │
└──────────────────────────────────────────────┘       └────────────────────────────────────────┘
```

---

## 🔒 Security & Privacy by Design

1. **HMAC-SHA256 Pseudonymization**:
   - Inbound phone numbers from WhatsApp, SMS, and IVR channels are immediately hashed using a private salt (`CITIZEN_REF_SALT`).
   - Raw phone numbers, device IDs, and personal contact details are **never stored** in any database table or log file.
2. **Accountless High-Entropy Token Tracking**:
   - Tracking tokens follow the format `JS-XXXX-XXXX` using an unambiguous 30-character alphabet ($30^8 \approx 6.56 \times 10^{11}$ combinations).
   - Tokens cannot be walked sequentially or enumerated by attackers.
3. **Zero-PII Officials Console**:
   - Officials view sanitized summaries, sector classifications, urgency levels, and scrubbed ward/village locations.
   - Even search queries across endpoints restrict leaking unscrubbed resident identifiers.

---

## 🤖 Google Gemini AI Integration & Model Pool

To ensure 100% operational uptime on free-tier Google AI Studio keys, JanSetu implements an automatic 7-tier model pool (`services/model_pool.py`):

1. `gemini-3.5-flash` (Primary)
2. `gemini-3.6-flash`
3. `gemini-3.7-flash`
4. `gemini-3-flash-preview`
5. `gemini-2.5-flash`
6. `gemini-3.5-flash-lite`
7. `gemini-3.1-flash-lite`

### Key AI Capabilities:
- **Multilingual Speech-to-Text & Translation**: Real-time voice transcription and bidirectional translation across 13 Indian languages + English.
- **Natural Language Structuring**: Extracts structured JSON containing sector category, urgency level (1–5), location hierarchy, and title.
- **Multi-Issue Splitting**: Automatically detects compound complaints (e.g., broken road + school damage) and splits them into distinct trackable tokens.
- **Deterministic Offline Fallbacks**: If AI services are unavailable or keys are omitted, deterministic keyword tokenizers and heuristic classifiers maintain full platform availability.

---

## 📊 Objective Priority Scoring Engine

Scoring is executed deterministically without LLM bias (`analytics/priority.py`):

$$\text{Priority Score} = 100 \times \left( 0.35 \cdot \text{Norm}(\text{Demand}_{\text{adj}}) + 0.30 \cdot \text{Norm}(\text{Coverage Gap}) + 0.20 \cdot \text{Norm}(\text{Deprivation}) + 0.15 \cdot \text{Norm}(\text{Underfunding}) \right)$$

- **Non-Linear Urgency Weighting**: $\{1: 0.5, 2: 0.75, 3: 1.0, 4: 1.5, 5: 2.5\}$
- **Participation Fairness Adjustment**: Low-literacy and low-internet districts receive up to $1.64\times$ multiplier to prevent digital exclusion.
