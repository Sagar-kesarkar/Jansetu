# Local complaint-limit implementation results

Verified 29 September 2026. The user has now authorised commit, push and deployment
after local validation. Hosting is not yet live. Baseline is `aa99ea7d841eca7871cf4b55215d20e3f501f217`,
“Refresh project documentation and rename citizen frontend”, committed
23 September 2026 at 19:55:08 IST on `github-publish`.

## Delivered behaviour

- Six persisted submissions per anonymous browser identity per day, resetting at
  midnight India time. Multiple cases extracted from one message count once.
- Server-side HMAC fingerprints block identical submissions while any associated
  case is still open. RESOLVED and REJECTED allow another submission; reopening
  an older matching case blocks it again. This is exact matching, not AI similarity.
- Signed random HttpOnly cookie identifies the browser without collecting a phone
  number or using IP/device fingerprinting. Backend transactions enforce capacity,
  duplicate checks and retry safety, including concurrent requests.
- A small dismissible notice appears after a submission or relevant error. The
  initial page has no quota banner. Success shows the used count and remaining
  allowance. Duplicate notices link to existing tracking receipts; errors preserve
  the draft.
- A theme-matched first-visit cookie dialog offers “Accept required cookies” and
  “Not now”. Either selection closes it; the choice is remembered. Cookie settings
  reopens it. Declining allows browsing/tracking but disables submission. No
  advertising or analytics categories are presented because none were added.
- Local tracking receipts and uncertain retry keys are bounded to 50 entries and
  90 days; raw complaint text/media are not saved in those receipt records.
  Forgetting local links does not erase server cases or reset server usage.
- Existing-schema migration adds the submission linkage and guard tables without
  deleting existing cases. Stable secret configuration is required.

## Verification performed

| Check | Result |
| --- | --- |
| Backend: `..\.venv\Scripts\python.exe -m pytest` from backend | 315 passed |
| Citizen: `npm test` | 9 passed |
| Citizen: `npm run build` | Passed |
| Admin: `npm run build` | Passed; existing large-chunk warning |
| Local backend `/health` and citizen page | Healthy / HTTP 200 |
| Git staged diff | Empty; baseline commit unchanged |

Backend coverage includes independent identities, first-six/seventh rejection,
nonterminal statuses, multi-case closure, reopened cases, exact media fingerprints,
idempotent replay and key mismatch, midnight reservation accounting, threaded and
separate-process concurrency, expired-worker fencing, rollback, restart persistence,
missing secret, cookie/consent boundaries, shared text/voice/report capacity and
legacy-schema preservation. Existing channel, tracking, location and casework tests
also pass. External services are mocked in automated tests.

Frontend unit checks exercise cookie-choice persistence and cross-tab changes,
storage failures, retry keys, receipt retention and keeping distinct tracking
receipts when identical content is filed again after closure. Browser walkthroughs
verified acceptance/decline, successful submission counts, duplicates, resubmission
after closure, quota exhaustion, restart persistence, mobile layouts and keyboard
focus. The mobile notice was moved below the navigation to avoid overlap.

## Preview and visual evidence

Citizen preview: <http://localhost:5173/>. Backend: <http://127.0.0.1:8080/health>.
The local preview uses a separate ignored `.local-preview` database, secret and
evidence directory, with reference districts and synthetic complaints. Gemini is
disabled for this preview; the normal project database is not used. Start commands
are documented in [RUN.md](../../RUN.md).

- [Desktop cookie dialog](feature-verification/cookie-desktop.png)
- [Mobile cookie dialog](feature-verification/cookie-mobile.png)
- [Submission count notice](feature-verification/submission-mobile.png)
- [Duplicate notice](feature-verification/duplicate-mobile.png)
- [Mobile daily-limit notice](feature-verification/limit-mobile.png)
- [Desktop daily-limit notice](feature-verification/limit-desktop.png)

## Limits and remaining release work

Brave follow-up (29 September): the user reported a blank citizen page with
`ERR_BLOCKED_BY_CLIENT` and identified the consent component. Renamed the
browser-loaded modules to `PrivacyPrompt.jsx` and `sitePreference.js`, preserving
consent behaviour and saved preferences. The user confirmed the page displays
after a hard refresh. Citizen production build and all 9 frontend tests passed
after the rename. No browser protection settings were changed.

This is a per-browser limit, not a guarantee of one identity per person. Deleting
cookies, using private browsing or another device can create a new identity.
Neither hashing nor local storage can prevent that without stronger identification.

Local SQLite and mocked-provider verification do not prove PostgreSQL, real provider
delivery or production cookie transport. Before Render/Netlify deployment, configure
durable database/media storage and a stable backend secret, verify migration and
restart behaviour there, and check browser cookie transport through the production
domain/proxy. No hosting accounts or production configuration were changed.

The funds coverage endpoint referenced the nonexistent `District.state_code`.
This was repaired during release preparation, with four additional regression
tests covering empty, state-only, district and unverified financial records.

Commit, push and deployment were explicitly authorised after final local review.
Actual publication and deployment outcomes must be verified separately.
