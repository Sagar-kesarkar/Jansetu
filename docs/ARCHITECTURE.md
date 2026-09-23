# Architecture

## Shape

```
Citizen                              Policymaker
  │ voice / text / WhatsApp / IVR      │ browser
  ▼                                    ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│ POST /intake/{voice,text,│   │ GET /hotspots            │
│      whatsapp}           │   │ GET /recommendations     │
└───────────┬──────────────┘   └───────────┬──────────────┘
            │                              │
            ▼                              ▼
   services/pipeline.py            analytics/aggregate.py
            │                              │
   ┌────────┴─────────┐                    ▼
   ▼                  ▼            analytics/priority.py   ← pure, deterministic
speech.py         gemini.py                 │
(Gemini audio)  (extract JSON)              ▼
   │                  │            analytics/explain.py
   └────────┬─────────┘                     │
            ▼                               ▼  gemini.py::write_policy_brief
      geocode.py → district           RecommendationOut + Evidence
            │
            ▼
        SQLite (no PII)
```

## Layering rule

`analytics/` never imports `services/`. Scoring is pure Python over plain
dataclasses — no I/O, no model calls, no framework. That is what makes it
testable and what makes the ranking auditable by someone who does not trust
LLMs. Gemini sits strictly at the edges: turning messy human input into
structure on the way in, and turning computed evidence into prose on the way out.

## The scoring model

`analytics/priority.py`. For each (district, sector) cell:

```
demand_adj   = weighted_demand_per_capita × participation_adjustment
score        = 100 × ( 0.35·norm(demand_adj)
                     + 0.30·norm(coverage_gap)
                     + 0.20·norm(deprivation)
                     + 0.15·norm(underfunding) )
```

Urgency is weighted non-linearly — `{1: 0.5, 2: 0.75, 3: 1.0, 4: 1.5, 5: 2.5}` —
because a collapsed bridge is not five times a pothole.

`participation_adjustment(literacy_pct, internet_pct)` returns a multiplier in
[0.15, 2.5]: a district at 48% literacy and 12% internet gets ~1.64×, one at
85%/60% gets 1.0×. Min-max normalisation runs across the queried set, so a
state-filtered query ranks districts against their own peers.

Because demand contributes at most 35 points, no amount of complaint volume
alone reaches the top of the list. Tested, not asserted.

## Degradation

Every Gemini call has a fallback. No key, quota exhausted, or a malformed
response → keyword extraction with `confidence: 0.1`, empty transcript, English
passthrough, or a deterministic rationale instead of a generated brief. The
dashboard keeps working and the ranking is unchanged, because the ranking never
depended on the model.

## Privacy

`CitizenRequest` stores an opaque `citizen_ref`, a district code, a category, an
urgency, the raw text and a summary. No name, phone number, address or
device identifier. Nothing in the schema can re-identify a citizen, so the
dataset is safe to publish as a public good.
