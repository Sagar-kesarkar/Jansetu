# JanSetu

Multilingual civic reporting and district-level public-service prioritisation for India.

JanSetu is a hackathon prototype with a citizen website, an officials console and a shared FastAPI backend. Citizens submit text, audio and photographs, receive request tokens, and follow case updates. WhatsApp, SMS and IVR adapters connect channel workflows to the backend.

## Current status

- Source: https://github.com/Sagar-kesarkar/Jansetu.
- Netlify deployment is deferred. Backend hosting is undecided.
- Both frontend production builds passed during publication preparation. Backend tests were not rerun for this documentation update; no fixed passing-test count is claimed.
- Officials sign-in is a browser-only demo gate, not production authentication.
- Financial adapters use bundled or hard-coded figures. These are demonstration inputs, not independently verified government accounts.
- Live provider delivery has not been verified in this review.

## Features

Text/audio/photo intake, grouped multi-issue requests, per-request JS-XXXX-XXXX tracking tokens, location follow-up, casework responses, invalid-request rescue, district/sector prioritisation, maps and demonstration public-funds views.

Thirteen languages are configured in total, including English: Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Punjabi, Odia, Assamese, Urdu and English.

Gemini uses google-genai. Fallback paths allow operation without a key, with reduced transcription, translation and extraction capabilities. Configured model names do not establish current availability, quotas or free-tier eligibility. No uptime guarantee is made.

## Technology

React 19, Vite 8, React Router, plain CSS, Leaflet/OpenStreetMap and Recharts; Python 3.12, FastAPI, Pydantic, SQLAlchemy and SQLite. No Tailwind. Gemini structures input and narrates evidence; ranking arithmetic is deterministic.

## Documentation

- [Local setup and verification](RUN.md)
- [Documentation index](docs/README.md)
- [Architecture](docs/architecture/ARCHITECTURE.md)
- [API reference](docs/api/API_REFERENCE.md)
- [Security and privacy](SECURITY.md)
- [Financial provenance](docs/data-sources/FINANCIAL_DATA_SOURCES.md)
- [Deployment preparation](docs/deployment/DEPLOYMENT.md)
- [Future Netlify configuration](docs/deployment/NETLIFY.md)
- [Contributing](CONTRIBUTING.md)

## Repository layout

| Directory | Purpose |
| --- | --- |
| frontend-citizen/ | Citizen website and policy views |
| frontend-admin/ | Officials console |
| backend/ | API, services, models, migrations and tests |
| data/ | Reference/demo datasets and reusable IVR prompts |
| docs/ | Technical and project documentation |
| infra/ | Legacy deployment examples; read its README before use |

Credentials, databases, citizen evidence, dependencies, build outputs and local archives are excluded from Git. Backend source is retained while hosting is undecided.

## Licence

[MIT](LICENSE).
