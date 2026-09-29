# Deployment preparation

The baseline was published previously. The current feature changes remain local
and uncommitted. Render backend and Netlify frontend preparation has started; see
[the release worksheet](RENDER_NETLIFY_RELEASE.md). No public application URL or
successful live channel delivery is claimed.

## Frontends

Follow [Netlify configuration](NETLIFY.md) when deployment is authorised. frontend-citizen/ and frontend-admin/ are independent static builds. Set VITE_API_BASE to the backend HTTPS URL before building; rebuild after changing it. Never place secrets in frontend variables.

## Backend container

The existing Dockerfile is single-stage and requires repository-root build context:

```sh
docker build -f backend/Dockerfile -t jansetu-api .
```

This is the intended invocation, not a verified container build. The image copies
only reference, synthetic and IVR assets, includes migration tooling, and does not
seed a database during build. The root .dockerignore excludes local credentials,
databases and evidence. Seed approved data once after durable storage is configured.

SQLite and evidence need durable storage, backups and a retention policy. Data baked into an image is not persistence for subsequent writes. Review automatic schema initialisation and Alembic together before upgrading a populated database.

## Configuration

Set DATABASE_URL, CITIZEN_REF_SALT, CORS_ORIGINS, PUBLIC_BASE_URL and, when needed, EVIDENCE_DIR. Gemini uses GEMINI_API_KEY, GEMINI_MODEL and GEMINI_MODEL_FALLBACKS. Model configuration does not guarantee current availability or free-tier access.

Channel credentials are additional to the Gemini key; see backend/app/config.py and .env.example. Check provider terms/charges before enabling live telephony or messaging. No paid setup is authorised here. Use [API reference](../api/API_REFERENCE.md) callback paths and complete real provider verification/delivery tests before claiming live support.

Read [SECURITY.md](../../SECURITY.md): the demo login does not protect APIs. Server-side access control and privacy handling must precede real citizen use.

Legacy infra scripts target Cloud Run/Firebase and do not implement the current deployment plan. Do not run them. Managed PostgreSQL and billed cloud services are not project requirements.
