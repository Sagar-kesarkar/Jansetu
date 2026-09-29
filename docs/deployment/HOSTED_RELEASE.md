# Competition deployment

- Citizen: https://jansetuu.netlify.app
- Admin: https://jansetuadmin.netlify.app
- Backend: https://jansetu-api-ckqj.onrender.com
- Feature baseline: `af7d1bb` (Cookie section: add consent and daily complaint limits).
- Budget pages, adapters, graphs and sync behavior remain identical to that baseline.
  The subsequently abandoned budget snapshot/source changes are not part of this release.

The citizen site proxies only session creation/revocation through `/backend`.
The HttpOnly, Secure cookie remains first-party. A confirmed cookie can obtain
an origin-bound five-minute ticket for direct API requests, avoiding Netlify's
26-second proxy timeout on AI processing. Tickets are hashed in PostgreSQL,
kept only in frontend memory and revoked when the cookie is declined.

Render uses PostgreSQL for complaints, quotas, tickets and photographs. Local
SQLite development continues using filesystem photographs. Hosted photo files
are a temporary read cache; the database retains the authoritative bytes.
Private Render database TLS uses `DATABASE_TLS_MODE=require`, as its internal
certificate is self-signed; external connections default to full verification.
Private settings live in Render's `/etc/secrets/jansetu.env`, never in frontend
builds or this repository. One-time seeding uses only reference/synthetic data.

The GitHub Actions health workflow runs every ten minutes and stops sending
requests after 15 October 2026 at 23:59 IST, the evaluation deadline. Variables
can override the URL/deadline or disable it with `BACKEND_HEALTH_ENABLED=false`.
Scheduled Actions can be delayed; this is not an uptime guarantee or backup.
The free database expires 29 October 2026 at 21:24 UTC (30 October 02:54 IST).
Export needed data before expiry; the health workflow cannot extend it.

This remains a competition demo: the existing admin login is a frontend demo
gate, not backend authorization. Do not use it for confidential real casework.
