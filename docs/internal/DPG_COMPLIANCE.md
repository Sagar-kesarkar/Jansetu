# Digital Public Good compliance

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

The track asks for a platform "designed as a Digital Public Good". The DPG
Alliance publishes nine standard indicators. Here is where JanSetu stands
against each, and where it honestly falls short of a production DPG.

| # | Indicator | Status |
|---|---|---|
| 1 | Relevance to an SDG | SDG 6 (water/sanitation), 9 (infrastructure), 10 (reduced inequality), 16 (accountable institutions) |
| 2 | Open licence | MIT — `LICENSE` |
| 3 | Clear ownership | Repo owner; no CLA barrier |
| 4 | Platform independence | Python + Docker + a standards-based REST API. No proprietary runtime. Gemini is swappable behind `services/gemini.py` |
| 5 | Documentation | `README.md`, `docs/`, and a live OpenAPI spec at `/openapi.json` |
| 6 | Data extraction mechanism | Every table reachable over the public API; JSONL export of the request corpus in `data/synthetic/` |
| 7 | Privacy and applicable law | No PII stored. Channels that carry an identifier (WhatsApp sends the sender's phone number) are pseudonymised with a keyed HMAC in `services/privacy.py` before persistence, enforced at the single `pipeline.ingest` choke point and covered by `tests/test_privacy.py` |
| 8 | Standards and best practices | LGD district codes, ISO 639 language codes, OpenAPI 3, national scheme taxonomy |
| 9 | Do No Harm by design | Participation adjustment exists specifically to stop the tool amplifying the digital divide; scoring is transparent and every recommendation ships its evidence |

## Everything is configuration, not code

A DPG has to be adoptable by a state that disagrees with your assumptions.
Three things a government adopter would want to change are all data, not logic:

- **Sector taxonomy** — `backend/app/models/taxonomy.py`
- **Languages** — `backend/app/i18n/languages.py`
- **Scoring weights** — `DEFAULT_WEIGHTS` in `backend/app/analytics/priority.py`,
  and `score()` accepts a `weights` override per call, so a ministry can retune
  the balance between citizen demand and coverage gap without a fork.

## Free and open source throughout

| Need | Choice | Why not the obvious alternative |
|---|---|---|
| Speech to text | Gemini native audio (free AI Studio tier) | Cloud Speech-to-Text v2/Chirp is billed and needs a billing account |
| Translation | Gemini (free tier) | Cloud Translation v3 is billed |
| Map | Leaflet + OpenStreetMap tiles | Google Maps JS API is billed after the free credit |
| Database | SQLite | Cloud SQL and BigQuery are billed |
| Hosting | Hugging Face Spaces / Netlify | Cloud Run's free tier still requires a billing account on file |
| Everything else | FastAPI, SQLAlchemy, React, Vite, rapidfuzz, pytest | all permissively licensed |

Total cost to run this project: ₹0, and one free API key.

## Where it falls short of a real DPG

Stated plainly, because claiming otherwise invites the question anyway:
no accessibility audit, no i18n of the dashboard UI itself (only of citizen
input and acknowledgements), no data-governance policy document, no
authentication or audit log on the policymaker views, and no independent
security review. These are the next milestones, not solved problems.

## Privacy and Data Minimization Architecture

JanSetu enforces zero-PII guarantees by design:
- **Phone Numbers / Inbound Sender Handles**: Any inbound caller ID or WhatsApp MSISDN is pseudonymised into a keyed HMAC (`citizen_ref`) at the single ingestion boundary and discarded immediately. Raw phone numbers are never persisted.
- **Evidence Photographs**: Photos attached via Web or WhatsApp are processed ephemerally in-memory by Gemini Vision for issue verification (`image_verification` summary). Raw image binary bytes are not persisted on production servers.
- **Locality & Addresses**: Location strings are normalized into scrubbed LGD district codes and ward aliases (`place_aliases.csv`), preventing home street address persistence while enabling district-level demand aggregation.
- **Accountless Tracking**: Status query tokens (`JS-XXXX-XXXX`) are randomly generated cryptographic identifiers independent of the reporter's HMAC, ensuring looking up a single case reveals zero reporter history.
