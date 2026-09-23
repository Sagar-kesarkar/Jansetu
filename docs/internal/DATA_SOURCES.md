# Data sources and provenance

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

Judges discount projects that blur real and synthetic data. This file draws the
line explicitly. Every number in the demo falls into exactly one of three
buckets.

## Real

`data/reference/districts.csv` — 46 districts across 18 states and union
territories. District names, state assignment, **Census 2011 population**,
**Census 2011 literacy rate** and approximate centroid coordinates are real.
Districts were selected to span all thirteen supported linguistic regions and to
over-represent aspirational districts, where the misallocation problem is
sharpest — but the set deliberately also includes well-off, well-connected
districts (Pune, Mumbai Suburban, Surat, Hyderabad, Lucknow). Without them the
platform could not demonstrate its central claim, which is a *contrast*: loud,
well-served districts against quiet, under-served ones.

`data/reference/place_aliases.csv` — the other names each district goes by:
cities, localities, tehsils, native-script spellings, former names (Osmanabad /
Dharashiv) and PIN codes. Locality and tehsil names are real and checkable
against the LGD directory. **The PIN codes are a hand-assembled sample**, not the
India Post directory — they cover the districts most likely to appear in a demo.
Substituting the full open India Post dataset is a CSV replacement with no code
change, which is why the table lives in `data/` rather than in the geocoder.

This file exists because of a real failure in the live system: a citizen
submitted "sector 23, ulwe, 410206 NAVI MUMBAI, MAHARASHTRA" and it did not
resolve, because nobody in India files a complaint using the name of their
district. They name their ward, their locality, their city, or they type a PIN.

The `code` column holds readable placeholders (`AS_BARPETA`). In production
these are **LGD (Local Government Directory) codes**, the Ministry of
Panchayati Raj identifier that central scheme dashboards already key on. Swap
the column and JanSetu joins directly against government data.

## Derived — deterministic, seeded, clearly labelled

`data/scripts/build_reference.py` (SEED=20260822) generates:

- `data/reference/infra_indices.csv` — scheme-wise coverage percentage per
  district per sector, anchored to the district's deprivation index so the
  relationship between deprivation and coverage is realistic.
- `data/reference/investment_plans.csv` — current allocation in ₹ lakh per
  district per sector.

**Allocation is deliberately inversely correlated with deprivation** — roughly
₹90 per capita in the best-off districts falling to ₹25 in the worst. That is
the misallocation the platform exists to surface. If the seed data did not
contain it, the demo would prove nothing.

In deployment these two tables come from the Jal Jeevan Mission dashboard,
Swachh Bharat Mission-G, PMGSY Online Management, the NITI Aayog Aspirational
Districts dashboard and state budget documents — all public. The schema matches
what those sources publish, so replacing the CSVs is a data task, not a code task.

## Synthetic — and biased on purpose

`data/scripts/generate_requests.py` produces `data/synthetic/citizen_requests.jsonl`:
600 citizen requests across 24 of the 46 districts in 8 languages, using genuine
native-script sentences rather than transliteration or translated English.

The 22 districts with no seeded requests are not an oversight. A district is
covered as soon as it is in `districts.csv` — it can receive reports, it has
coverage and allocation figures — but it earns a place in the ranking only when
citizens actually report from it. That is the honest behaviour: the platform does
not invent demand for a district nobody has written from yet.

Two properties matter:

1. **Volume is skewed by connectivity.** Request count scales as
   `internet_pct^1.6 × population^0.35`. Well-connected districts generate far
   more reports. This reproduces the exact bias that makes volume-ranked
   grievance portals misallocate money, and it is what the participation
   adjustment in `analytics/priority.py` corrects.
2. **Ground truth is retained.** Each record carries `category_hint` and
   `urgency_hint`, so the same corpus doubles as an evaluation set for
   extraction accuracy.

Channel mix reflects Indian usage: WhatsApp 42%, voice 25%, web text 18%,
IVR 10%, SMS 5%.

## Telephony and Messaging Channels — Real vs Simulated

- **WhatsApp Cloud API**: Real and free via Meta developer sandbox numbers. Receives text, voice notes, and photographs, and returns native-script acknowledgements.
- **IVR Feature-Phone Line**: Inbound Indian DID phone numbers are not free on any cloud telephony provider (Twilio, Exotel, Plivo). To preserve the **₹0 infrastructure / no credit card** constraint, the IVR channel is demonstrated against a provider-agnostic HTTP simulator (`POST /ivr/simulate`) and pure state machine (`backend/app/channels/state.py`). The webhook adapter (`POST /ivr/webhook`) directly emits Twilio TwiML XML and Exotel JSON payloads without requiring any paid SDKs. See [TELEPHONY_ADAPTERS.md](TELEPHONY_ADAPTERS.md).

## One honest caveat about seeding

`backend/app/db/seed.py` bulk-inserts the 600 requests using their hints. It
does **not** call Gemini, because 600 sequential model calls would burn free-tier
quota and take minutes.

The live `/intake/*` and `/ivr/*` endpoints always call Gemini for real. So: seeded history
is pre-labelled, anything submitted during the demo is genuinely classified by
Gemini in front of the judge.

Say that plainly in the video. Stated openly it reads as rigour; glossed over,
it reads as hand-waving.
