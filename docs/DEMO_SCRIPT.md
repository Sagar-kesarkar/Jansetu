# Demo video script — 3 to 5 minutes

Target 4:15. Screen recording with voiceover. Show the product working; do not
narrate a slide deck. Rehearse once with a stopwatch.

Before recording: `make seed`, start API and web, open the dashboard, hard-refresh,
have a phone ready to record one Hindi voice note, and **hit the deployed URL once**
so it is warm.

---

**0:00–0:25 — The problem, stated as a number**

> "India's grievance portals rank problems by how many people complain. That
> sounds democratic. It isn't. Complaint volume tracks internet access, not need."

Show two districts side by side on the dashboard. One has 400 complaints, 92%
water coverage. The other has 40 complaints, 28% coverage. Point at them.

> "The second district needs the money. It will never win a queue sorted by volume."

**0:25–0:50 — What JanSetu is**

> "JanSetu takes citizen reports in 13 Indian languages by voice, text or
> WhatsApp, and weighs them against infrastructure coverage, deprivation and what
> the government is already spending. It's an open-source Digital Public Good."

**0:50–1:50 — Citizen journey, live**

Open the citizen page on a phone-width window. Press record. Speak an actual
Hindi sentence:

> "हमारे गाँव में पानी नहीं आ रहा है, तीन महीने से हैंडपंप खराब है।"

Show the response arriving:

> "Gemini transcribed that audio, pulled out the sector — water supply — the
> urgency, and the location, and wrote an English summary so the request can be
> compared with reports from Tamil Nadu or Assam. The citizen gets an
> acknowledgement back in Hindi."

Then, one line that earns trust:

> "No name, no phone number, no address is stored. Just a district and a need."

Repeat once in Tamil or Bengali to prove multilingual is real, not a dropdown.

**1:50–3:10 — Policymaker journey**

Switch to the dashboard. Map with hotspots. Filter to a state.

> "Every district-sector pair gets an unmet-need score. Citizen demand is only
> 35% of it. Coverage gap is 30, deprivation 20, underfunding 15."

Open the top recommendation and read its evidence panel aloud:

> "Nabarangpur, water supply. 33% coverage — a 67-point gap. ₹39 per capita
> allocated, against ₹45 averaged across every district in the set, and this is
> the most deprived district on the list at 0.89. And the participation
> adjustment: 1.49, because at 12% internet penetration and 46% literacy, the
> four reports we got represent far more unmet need than four reports from a
> connected district."

Verify these figures against the live API before recording — `GET
/recommendations?limit=1` prints all of them. They move whenever
`data/scripts/build_reference.py` is re-run, and reading a stale number aloud on
camera is the one error a judge cannot un-hear.

> "Gemini writes this brief — but from our numbers. The scoring is deterministic
> Python. The model narrates the evidence; it never invents it."

Then the moment that separates this from a dashboard:

> "It maps to Jal Jeevan Mission, with an estimated beneficiary count. That's not
> an insight. That's a budget line."

**3:10–3:40 — The gaming test**

> "An obvious objection: can a district organise a complaint drive and jump the
> queue?"

Show the test passing.

> "We inflate demand twenty-fold in our test suite. The ranking doesn't move,
> because demand can contribute at most 35 points out of 100. Need beats noise
> by construction."

**3:40–4:15 — Scale and close**

> "The unit is the district, keyed to LGD codes — the same identifier every
> central scheme dashboard already uses. 46 districts across 18 states today;
> adding the rest of India is adding rows to a CSV, not writing code."

> "Runs on one free Gemini API key. MIT licensed. Because the point of a Digital
> Public Good is that a state government can fork it on Monday."

---

## Things to cut if you run long

The Tamil repeat (keep Hindi), the state filter interaction, and the beneficiary
estimate. **Never cut** the participation adjustment explanation or the gaming
test — they are the two things no competing submission will have.
