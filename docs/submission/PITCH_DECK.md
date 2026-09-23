# JanSetu (जनसेतु) — Pitch Deck (12 Slides)

`JanSetu — AI for Digital Public Infrastructure and Governance`

---

### Slide 1: Title & Vision
- **Header**: JanSetu (जनसेतु)
- **Tagline**: AI-Powered Digital Public Infrastructure for Equitable Grievance Redressal & Public Funds Transparency.
- **Presenter**: JanSetu Development Team
- **Core Value**: Transforming citizen voice into accountable governance across 13 Indian languages.

---

### Slide 2: The Problem
- **The Challenge**: 600M+ non-English speaking citizens in India face severe digital and linguistic exclusion when filing public grievances.
- **Key Pain Points**:
  - Complex English-first online portals requiring typing and OTP verification.
  - Multi-issue grievances getting lost in departmental silos.
  - Opaque black-box processing with no public funds transparency or verifiable budget tracking.

---

### Slide 3: Target Communities Served
- **Rural & Semi-Urban Citizens**: Speaking regional Indian languages (Hindi, Marathi, Tamil, Telugu, Bengali, Odia, etc.).
- **Feature Phone & Low-Bandwidth Users**: Accessible via toll-free IVR voice calls and SMS.
- **Civic Administrators & Local Government**: Municipal officers, district collectors, and department heads requiring structured triage.
- **Civil Society & Policy Researchers**: Tracking civic demand against actual government expenditure.

---

### Slide 4: The JanSetu Solution
- **Omnichannel Intake**: Web, WhatsApp, SMS, and IVR voice telephony.
- **AI-Powered Structuring**: Automatic dialect transcription, sector categorization, and urgency scoring via Google Gemini.
- **Mandatory Location Gating**: Geocoding against Local Government Directory (LGD) codes and 542 geographic aliases.
- **Zero-Barrier Tracking**: Accountless, high-entropy tokens (`JS-XXXX-XXXX`) with real-time multilingual stage progression.

---

### Slide 5: End-to-End Citizen Journey
```
[Citizen Voice/Text] ➡️ [Gemini Structuring & Verification] ➡️ [Token Issuance]
         ⬇️                                                        ⬇️
[Official Actions & Replies] ⬅️ [Casework Queue (:5174)] ⬅️ [Database Record]
         ⬇️
[Citizen Real-Time Multilingual Tracking (:5173)]
```

---

### Slide 6: Google Gemini AI Architecture
- **Multimodal Intelligence**: Speech-to-text for audio recordings, image understanding for photographic evidence.
- **Multi-Issue Segmentation**: Splitting complex compound statements into separate actionable tickets.
- **7-Tier Resilient Model Pool**: Automatic escalation across 7 Gemini models ensures 100% uptime within AI Studio free-tier quotas.
- **Deterministic Safeguards**: Heuristic keyword fallback ensures the platform never fails even during network disruptions.

---

### Slide 7: Omnichannel & Multilingual Access
- **13 Indian Languages Supported**: Assamese, Bengali, English, Gujarati, Hindi, Kannada, Malayalam, Marathi, Odia, Punjabi, Tamil, Telugu, Urdu.
- **Voice & Telephony**: Interactive Voice Response (IVR) with pre-recorded audio prompts; conversational WhatsApp and SMS chatbots.
- **Zero-Barrier Inclusivity**: No login, password, or Aadhaar requirement — high-entropy tokens provide secure, privacy-preserving tracking.

---

### Slide 8: Officials Console (Casework Desk)
- **Zero-PII Privacy Protection**: Eliminates citizen surveillance risks; shows only scrubbed locality, urgency, and category.
- **Live Casework Queue**: Real-time Server-Sent Events (SSE) stream for new incoming complaints.
- **Multilingual Bidirectional Replies**: Officials draft in English or regional languages; Gemini auto-translates replies into the citizen's native language.

---

### Slide 9: Authoritative Public Funds Transparency
- **4-KPI Financial Tracking**: Total Allocated, Funds Released, Recorded Expenditure, and Available Balance.
- **Strict Accounting Precedence**: Revised Estimates (`RE`) supersede Budget Estimates (`BE`); Audited Actuals (`ACTUAL`) supersede provisional payments.
- **Verified Sources**: Ingestion from Maharashtra State Finance, Open Government Data (OGD) India, and eGramSwaraj.

---

### Slide 10: Technical Architecture & Deployment
- **Backend**: FastAPI, SQLAlchemy, SQLite (Dev) / PostgreSQL (Prod), Docker containerized.
- **Frontend**: React 19, Vite, Leaflet mapping, Recharts data visualization.
- **Robust Testing**: 280 automated Pytest test suite covering core ingestion, security, state machines, and financial precedence.

---

### Slide 11: Scaling Across India
- **LGD Directory Standard**: Compatible with 700+ Indian districts and village codes.
- **State Modular Configuration**: Seamlessly onboard new states with localized budget schemas and regional language models.
- **Cloud-Native & Low Overhead**: Designed for national deployment on Indian Digital Public Infrastructure (DPI).

---

### Slide 12: Impact, Next Steps & Conclusion
- **Measurable Impact**: Equal access for 1.4B citizens, faster grievance turnaround, and radical public spending accountability.
- **Next Milestones**: Integration with DigiLocker for optional verified claims and state-wide rollout pilots.
- **Closing**: *JanSetu — Empowering every Indian voice through equitable, transparent AI.*
