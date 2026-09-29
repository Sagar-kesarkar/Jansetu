# Daily submission limits and exact duplicate recognition

Status: implemented and verified locally on 29 September 2026. See the
[implementation report](COMPLAINT_LIMIT_IMPLEMENTATION_REPORT.md) for actual coverage,
screenshots and remaining deployment checks. Commit, push and deployment now
authorised after the final local validation.
Prepared: 28 September 2026.
Target: approximately 10 hours of implementation and local verification, excluding
GitHub approval, remote publishing, account setup and deployment.

## Agreed delivery sequence

1. Save this reviewable plan.
2. Implement locally, preserving existing work and data.
3. Run automated regression checks and browser verification; repair failures.
4. Present actual results and the final diff. Do not commit until explicitly authorised.
5. Update GitHub only after explicit push approval.
6. Prepare Render backend and Netlify frontend deployment as a separate final stage.

Ten hours is an effort estimate, not a guarantee of completion or an instruction
to delay completed work. Do not claim background execution or overnight tests
unless they have actually run. Record unfinished work if the estimate is exceeded.

## Product contract

- Six successfully persisted submissions per anonymous reporter per calendar day,
  resetting at midnight Asia/Kolkata using server time. Limit is configurable.
- One submitted message counts once even when extraction creates several cases.
- Tracking, requested location updates, blocked duplicates, validation errors and
  technical failures do not consume another allowance.
- Persisted INVALID submissions count; conversational turns with no filed record
  do not. Separate attempt throttling protects expensive processing.
- An identical submission by the same reporter is blocked until every associated
  case is RESOLVED or REJECTED. This includes NEW, ACKNOWLEDGED, UNDER_REVIEW,
  ASSIGNED, IN_PROGRESS, NEEDS_LOCATION and INVALID as blocking states.
- For NEEDS_LOCATION, link to supplying location. For INVALID, show the existing
  triage outcome; do not equate automatic classification with human rejection.
- A new identical submission after closure consumes one current-day allowance.
- Reopened cases block another identical submission again. Check all matching
  groups, not only the newest one.
- Other reporters may submit the same content. No cross-reporter tracking links
  or identity information may be returned.
- Changing content permits a new submission, still subject to the daily limit.
- Duplicate detection remains active across midnight; only daily usage resets.

## Identity and privacy

Use a server-issued random browser token, protected against forgery, in an
HttpOnly cookie. Use HMAC with a stable backend-only secret for database identity.
Do not use phone collection, IP tracking, browser fingerprinting or hardware IDs.
The user explicitly requested browser remembrance; update the existing privacy
copy and contributor guidance narrowly to explain this new pseudonymous token.
Do not retain the current claim that only district information is kept.

The guarantee is per anonymous browser identity, not per human. Deleting that
cookie, private browsing or another device can create another identity. Deleting
local receipt storage alone must not bypass backend checks.

Keep browser identity separate from public per-case tracking tokens. Never return
the secret or stable server identity to the client. Do not log cookies or receipts.
Keep the secret stable across restarts and workers; do not silently use the current
process-local ephemeral secret for durable quota identity.

Establish identity before enabling submission. Browser requests cannot select
their quota identity through citizen_ref or a claimed channel. Trusted provider
webhooks retain verified sender identity and their current event deduplication.
Do not promise linking a website visitor with a messaging sender.

Choose a bounded cookie/receipt retention period and document it during implementation.
Bound browser storage and expire old usage/processing records without deleting cases.
Do not discard active duplicate indexes merely because a daily counter expires.

## Exact matching and local remembrance

Fingerprint the original accepted text, location, language, media types and
attachment bytes using a versioned, unambiguous encoding and keyed digest.
Exclude filenames, transport route, generated summaries and request timestamps.
Do not apply semantic matching, case folding or whitespace collapsing. Reconcile
the form's existing edge trimming so the comparison uses precisely what is sent;
make no new hidden content normalization.

Identical uploaded bytes match; a fresh recording or recompressed photo may not.
Official edits and later location clarification do not mutate the original
submission fingerprint. Legacy cases without original media/fingerprint cannot
be fully reconstructed: retain them without claiming retroactive exact matching.

Remember a bounded local receipt containing an opaque fingerprint and tracking
references, not copies of complaint text/photos/audio. Store only after a confirmed
result. The backend is authoritative for duplicates and current case statuses.
Handle blocked/full/corrupt browser storage gracefully. Treat saved tracking
references as bearer receipts and explain shared-browser visibility.

## Backend implementation

Inspect and extend app/services/privacy.py, services/pipeline.py, db/models.py,
routers/intake.py, models/schemas.py and config.py; inspect all callers of ingestion,
including simulators and provider adapters, before editing.

Add durable daily usage, original submission/group linkage, and processing/retry
records. Use unique constraints and transactional conditional updates; a separate
count-then-insert is insufficient. Preserve SQLite locally and design for PostgreSQL.
Add an additive migration; never drop or reseed the user's existing database.

Processing order:

1. Validate identity, retry key, content/size and separate attempt throttle.
2. Return a completed retry's original result; reject key reuse with changed payload.
3. Check same-reporter exact duplicates, returning the existing tracking details.
4. Atomically claim the fingerprint and reserve daily capacity.
5. Perform expensive extraction outside a long-lived database write lock.
6. Persist the submission, case links and final usage consistently.
7. On failure release the reservation; recover abandoned work with bounded leases
   and fencing so a late worker cannot finalise a reclaimed reservation.

Handle simultaneous requests, multiple processes, day rollover during processing,
and response loss after commit. Charge the day on which capacity was reserved;
retries must not charge again. Never automatically replay an uncertain complaint
with a fresh retry key.

Expose structured quota metadata (limit, used, remaining, reset_at), duplicate
metadata and retry-safe results. Return 429 for quota exhaustion, 409 for a blocked
duplicate, and distinguish already-processing submissions. Include Retry-After
where appropriate. Quota discovery must not reveal another reporter's records.

Apply checks consistently to /intake/report, /intake/text, /intake/voice and
browser-accessible channel simulation paths. Preserve existing provider event
idempotency; exercise trusted sender paths in regression tests.

## Frontend and visual requirements

Extend src/api.js and pages/CitizenIntake.jsx and reuse existing States,
IntakeResultCard, CSS variables, card and button styles. Do not add a new UI framework.

- Show remaining submissions and reset time from server metadata only after an
  attempt, in a small dismissible top-right notice; no front-page quota banner.
- Show duplicate status with existing tracking link(s).
- Show a daily-limit notice without losing entered text or attachments.
- Preserve the same retry key across an uncertain network result.
- Refresh allowance after submission, page return and day rollover; no stale
  local counter may authorise a submission.
- Use a themed cookie dialog on the first visit, with Accept required cookies and
  Not now. Remember the choice and provide Cookie settings to reopen it. Declining
  permits browsing and tracking, while submission requires the identity cookie.
- Notices and dialogs must match the page's colours,
  fonts, spacing, corners, shadows and button hierarchy; no window.alert/confirm.
- Do not display saved submissions as if they were all still pending. Use live
  status or clearly indicate status could not be refreshed.
- Match existing language conventions and centralise new copy. Check longer
  messages, mobile widths, readable contrast and non-colour status cues.
- Use accessible live regions, labelled controls and keyboard-visible focus.
  Dialogs, if used, need focus management and dismissal behaviour.

Credentials/CORS/cookie behaviour must be tested locally. For final Netlify/Render
hosting, verify a same-site/proxied API or appropriate domains rather than relying
blindly on third-party cookies. HTTPS cookie settings must have an explicit local
development configuration.

## Local acceptance checklist

The original checklist below is retained as the planned coverage inventory, not
an assertion that every permutation was exercised. Completed checks and their
scope are recorded in the implementation report.

- [ ] First six succeed; seventh fails; another reporter remains independent.
- [ ] Midnight IST and concurrent midnight submissions behave as specified.
- [ ] Same content is blocked for every nonterminal state, including INVALID and
      NEEDS_LOCATION; only wholly closed groups permit resubmission.
- [ ] Duplicate remains blocked on a new day; reopened matching cases block again.
- [ ] Changed text/location/language/media works; identical files with changed
      filenames still match; no semantic matching is introduced.
- [ ] Duplicate at an exhausted quota still returns the existing receipt.
- [ ] Concurrent duplicate attempts create one group; concurrent distinct attempts
      cannot exceed daily capacity, including separate DB connections/processes.
- [ ] Failed processing, lease recovery and late worker completion cannot leak or
      double-charge capacity; server restart preserves completed usage.
- [ ] Lost response/double-click/retry returns the existing result without a new AI call.
- [ ] Invalid/tampered identity, cookie rejection, spoofed channel/citizen_ref and
      deleted local receipts do not bypass the applicable browser rules.
- [ ] Missing/corrupt browser storage, multiple tabs and failed status refresh work.
- [ ] Tracking/location updates and existing provider retries are unchanged.
- [ ] Existing backend suite passes with external services mocked.
- [ ] Citizen and admin production builds pass.
- [ ] Actual local browser walkthrough covers success, remaining count, duplicate,
      quota limit, failure, resubmission after closure, mobile and keyboard states.
- [ ] Capture visual evidence of new notices and compare with existing page theme.
- [ ] Database migration preserves a disposable copy of existing-schema data.

Use isolated test databases and temporary evidence paths. Never consume the user's
daily quota or real evidence for automated tests. Log commands and actual results;
separate mocked AI/simulator coverage from any real provider verification.

## Approximately 10-hour work allocation

| Work | Budget |
| --- | --- |
| Baseline checks, route audit, theme audit and migration design | 1 hour |
| Identity, database records, quota and atomic duplicate/retry handling | 3 hours |
| Frontend receipt storage, notices and existing-theme integration | 2 hours |
| Automated tests, concurrency/failure checks and fixes | 2 hours |
| Browser/mobile/accessibility verification and both frontend builds | 1 hour |
| Final regression review, documentation and reviewable change summary | 1 hour |

Record progress and test outcomes in a companion implementation report. Do not
skip correctness checks to meet the estimate. Surface blockers with concrete
evidence; account access and publication approvals are outside this budget.

## Later deployment gate

After local completion and GitHub approval, choose persistent database and photo
storage before deploying on Render Free. Local SQLite in its temporary filesystem
is not sufficient. Test production cookie transport and persistence after restart.
Netlify remains the frontend target. A scheduled external call to the existing
lightweight /health endpoint is optional for reducing idle delays, not durability.
CAPTCHA, cross-device identity and broad production-auth work are separate scope.
