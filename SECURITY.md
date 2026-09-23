# Security and privacy

## Current boundary

JanSetu is a hackathon demonstration. Officials sign-in runs in the browser using shipped demo credentials and does not authenticate API requests. Casework read/write and photo routes require server-enforced authentication, authorisation and jurisdiction checks before real citizen use. CORS is not authentication.

Public tracking tokens are bearer references. Randomness reduces sequential guessing but does not make enumeration impossible or replace rate limiting. Do not publish real tokens in screenshots or logs.

## Data handling

The intended policy is no direct citizen identifiers. Channel sender identifiers are pseudonymised with HMAC-SHA256; keep CITIZEN_REF_SALT private and stable. Sender values may be needed transiently for provider replies. Free text and photographs may still contain personal information; pseudonymisation is not proof that all content is anonymous.

The current implementation retains uploaded photographs through services/evidence.py and serves them at GET /requests/{request_id}/photo. Files are named by request token and excluded from Git. A non-static storage directory does not enforce access control. Do not assume faces, labels or metadata are redacted. Retention duration and automated deletion require an explicit policy before real use. Earlier claims that all image bytes are discarded are obsolete.

Gemini and channel providers may receive submitted content during processing. Explain this before production use. Do not promise end-to-end zero-PII guarantees without validating all processing paths.

## Deployment

Keep credentials only on the backend. VITE_* values are public JavaScript configuration. Exclude environment files, databases and evidence from Git and container build contexts. Implement HTTPS, request limits, provider verification, durable storage and backups before real deployment.

## Vulnerability reporting

Do not post credentials or personal data in public issues. Use GitHub private vulnerability reporting if enabled, or request a private contact in an issue containing no sensitive details. A dedicated security email and response SLA have not been established.
