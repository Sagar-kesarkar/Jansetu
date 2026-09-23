# Architecture

## Components

frontend-citizen/ and frontend-admin/ are independent React/Vite websites using one FastAPI application in backend/app/main.py. SQLite stores requests, responses, sessions, webhook events and financial records. Maps use Leaflet/OpenStreetMap; styles use plain CSS.

## Intake

Web and channel adapters share services/pipeline.py. Gemini extracts structured issues; backend validation, location resolution, token generation and persistence remain server responsibilities. IntakeEnvelope extends the legacy result and exposes multiple request results. Each split issue receives a row and token; siblings share submission_group_id.

Classification distinguishes single/multiple issues, clarification, missing location and invalid/spam input. NEEDS_LOCATION rows are held out of actionable demand. Location follow-up preserves the selected token. NEW is the initial stored casework status presented as submitted. INVALID rows may remain available for rescue without a normal public token. Classification does not prove whether a reported event occurred.

ChannelEvent deduplicates webhooks; original_message_id links intake retries. Channel location updates must verify pseudonymised sender ownership. The console uses /requests; a parallel /official surface includes SSE events.

## Analytics

analytics/ must not import services/. Ranking is deterministic:

score = 100 × (0.35 × norm(adjusted demand) + 0.30 × norm(coverage gap) + 0.20 × norm(deprivation) + 0.15 × norm(underfunding)).

Urgency weights: {1: 0.5, 2: 0.75, 3: 1.0, 4: 1.5, 5: 2.5}. Participation adjustment is bounded by 0.15 and 2.5. Normalisation is across the queried peer set. Gemini does not calculate scores; extracted classifications and urgency still influence input evidence and require validation.

Coverage is data-driven. Symbolic identifiers such as MH_PUNE should not be described as numeric LGD codes without a verified mapping.

## Persistence and configuration

init_db() creates tables and applies additive missing columns/indexes. Compatible added columns must be nullable or have server defaults. Alembic also contains a financial-table migration. Review these overlapping paths and back up databases before upgrades; do not blindly apply both to existing tables.

The settings variable REPO_ROOT currently resolves to backend/. Reference copies exist in data/reference and backend/data/reference; reconcile them when updating coverage. Relative SQLite URLs depend on the process working directory.

## Limitations

Fallbacks offer reduced capability, not guaranteed uptime. Financial adapters use demo inputs. Uploaded photos are retained. Officials sign-in is a demo gate. See [security](../../SECURITY.md) and [financial provenance](../data-sources/FINANCIAL_DATA_SOURCES.md). Backend hosting is undecided.
