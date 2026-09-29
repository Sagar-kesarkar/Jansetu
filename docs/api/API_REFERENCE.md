# API reference

The running /openapi.json and /docs describe payloads, parameters and schemas. The browser middleware requirements below also apply and are not all represented in OpenAPI. All paths below are relative to the backend URL.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /intake/report | Multipart text/audio/photo intake |
| POST | /intake/text | JSON text intake |
| POST | /intake/voice | Voice intake |
| GET | /track/{token} | Public tracking |
| PATCH | /track/{token}/location | Token-specific location follow-up |
| GET | /requests | Casework list |
| GET | /requests/stats | Casework statistics |
| GET | /requests/{request_id} | Case details |
| GET | /requests/{request_id}/photo | Retained photograph |
| POST | /requests/{request_id}/responses | Official reply |
| PATCH | /requests/{request_id}/status | Update status |
| PATCH | /requests/{request_id}/restore | Rescue invalid request |
| GET | /official/requests | Parallel officials feed |
| GET | /official/dashboard/summary | Summary |
| GET | /official/events/stream | SSE events |
| GET | /districts | District reference data |
| GET | /states | State options |
| GET | /hotspots | Demand aggregation |
| GET | /recommendations | Computed priorities |
| GET | /recommendations/brief | Narrative evidence |
| GET | /health | Health check |
| GET | /capabilities | Configuration/capabilities |

## Browser submission session

After explicit cookie acceptance, call GET `/intake/session` with
`X-Submission-Consent: required` and credentials included. The response contains
`confirmed` and `quota`; a new session sets the HttpOnly `jansetu_visitor` cookie.
Repeat with that cookie to confirm transport before enabling submission. POST
`/intake/session/revoke` removes the cookie. Both responses use `Cache-Control: no-store`.

The three intake endpoints require the cookie and an `Idempotency-Key`. Reuse the
key for retries of the same uncertain submission; use a new key for a new attempt
after a confirmed result. Browser IVR simulation paths also require the cookie.
An Origin header, when supplied, must match the configured allowlist.

Errors use structured `detail` objects: 428 for required consent/session, 422 for
a missing intake retry key, 403 for a disallowed origin, 409 for an active duplicate,
in-progress attempt or reused key with changed content, and 429 for daily capacity
or attempt throttling. Missing submission-secret configuration fails closed with
503. Successful intake envelopes may include `quota` and `fingerprint`.

Six persisted submission groups are allowed per browser identity per India calendar
day. Exact open duplicates are checked before the daily limit; all linked cases
must be RESOLVED or REJECTED before a fresh identical submission. Tracking and
location follow-up do not consume another allowance. See the implementation report
for anonymous-identity limitations and local validation coverage.

## Channels

- GET /intake/whatsapp: Meta verification challenge; POST on the same path: inbound webhook.
- GET or POST /intake/sms/exotel: SMS inbound.
- GET or POST /callbacks/sms/exotel/status: SMS callback.
- POST /ivr/webhook and /ivr/webhooks/incoming: IVR inbound.
- GET or POST /ivr/exotel/passthru: Exotel call-flow callback.
- POST /ivr/exotel/recording: recording callback.
- /ivr/sessions and per-session dtmf, input, audio, repeat and end routes support simulation. Consult OpenAPI for methods and bodies.

The IVR router is also mounted under /api/v1, exposing /api/v1/ivr/... aliases. Provider callbacks need the public backend URL and provider-side configuration.

## Funds

Public GET endpoints are /api/v1/funds/overview, /api/v1/funds/districts, /api/v1/funds/sectors, /api/v1/funds/sources and /api/v1/funds/coverage. Legacy allocations use /budget/allocations. Import/review routes are under /api/v1/admin/funds. A route name is not evidence of authentication or verified provenance.

Use request_count and requests for multi-issue intake; do not assume the top-level legacy result includes every issue. Stored NEW means submitted; NEEDS_LOCATION requires input. Tokens are bearer references. Read [security limitations](../../SECURITY.md) before exposing administrative or casework APIs.
