# Pitch deck outline — 11 slides

One idea per slide. Numbers, not adjectives. Build in whatever tool you like;
ask for a .pptx and it can be generated from this outline.

**1 — Title.** JanSetu / जनसेतु. "Turning citizen voices into a national
development plan." Track 01, AI for DPI & Governance. Name, live URL, repo URL.

**2 — The problem.** "Grievance portals rank by volume. Volume measures internet
access, not need." Two-district comparison: 400 complaints at 92% coverage
versus 40 complaints at 28% coverage. Ask the question: which one gets funded?

**3 — Why this persists.** The districts with the greatest need have the lowest
literacy and connectivity, so they file the fewest reports. Volume-ranked systems
therefore route money away from need, every cycle. Show internet penetration
against deprivation for the 24 seed districts.

**4 — The insight.** Citizen demand is evidence, not a ranking. Weight it, adjust
it for who could realistically have reported, and cross-check it against coverage,
deprivation and current spend.

**5 — How it works.** The one architecture diagram: intake in 13 languages →
Gemini structuring → join with demographics, infra indices and investment plans
→ unmet-need index → ranked recommendations. Keep it to five boxes.

**6 — Citizen experience.** Phone screenshot, actual Devanagari text, voice note,
acknowledgement in Hindi. Footnote: no PII stored.

**7 — Policymaker experience.** Dashboard screenshot: hotspot map plus the
evidence panel of the top recommendation.

**8 — The unmet-need index.** The four weights, the urgency curve, and the
participation adjustment with a worked example (1.64× at 48% literacy / 12%
internet). This is the intellectual core of the submission — give it a full slide.

**9 — Why it can't be gamed.** The 20× demand-inflation test, and the resulting
ranking that doesn't move. Screenshot the passing test.

**10 — Built for India, built to scale.** District-level, LGD-keyed, taxonomy
mapped to nine national schemes, 46 districts across 18 states in the seed, state
filtering that ranks peers against peers. Adding a district is adding CSV rows —
and the reference generator is seeded per district, so adding one cannot move an
existing district's numbers.

**11 — Digital Public Good, and cost.** MIT licence, open OpenAPI spec, weights
and taxonomy as configuration, privacy by design. Runs on one free Gemini key —
₹0 infrastructure cost. Close on the fork-on-Monday line.

*Optional 12 — Roadmap:* real LGD ingestion, WhatsApp Business API, offline IVR
at scale, accessibility audit, state pilot.

## Design notes

Use the map and the evidence panel as the two hero visuals. Avoid stock photos of
villages — they read as filler. Every slide should survive being read aloud in
20 seconds.
