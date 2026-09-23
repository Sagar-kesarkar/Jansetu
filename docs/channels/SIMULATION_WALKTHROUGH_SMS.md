# Simulation Walkthrough — SMS

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

Simulate an inbound **SMS complaint** from the terminal — no gateway, no DLT
registration, no credentials — and watch it land on the **officials' admin
dashboard** with:

- **Language translation** — the SMS shows in English (`summary_en`) with the citizen's original text (Roman or native script) underneath (`raw_text`).
- **City / State** — the "Place" column resolves to a real district + state.

> **No audio / mp3 for SMS.** SMS is a text-only channel — there is no voice, so
> the "audio → text" demo does **not** apply here. Use it in the
> [WhatsApp](SIMULATION_WALKTHROUGH_WHATSAPP.md) and
> [IVR](SIMULATION_WALKTHROUGH_IVR.md) walkthroughs. For SMS, the AI still does
> the useful work of **translating** the message to English and **resolving the
> location**.

> Third of three files.

---

## 0. Prerequisites (same as the other two channels)

Do these once. (Full detail in the WhatsApp doc, §0.)

```bash
cd "D:/AI Code for Communities/jansetu/backend" && python -m app.db.seed
```
```bash
cd "D:/AI Code for Communities/jansetu/backend" && uvicorn app.main:app --reload --port 8080
```
```bash
cd "D:/AI Code for Communities/jansetu/frontend-admin" && npm install && npm run dev
```

Open **http://localhost:5174** and sign in as **`state.cell`** / `jansetu@2026`
(sees every state; a fresh complaint shows at the top). Seeding is what makes the
**city/state** resolve — use place names the seed knows: **Sitamarhi** (Bihar),
**Nabarangpur** (Odisha), **Pune** (Maharashtra). Translation uses the
`GEMINI_API_KEY` already present in `jansetu/.env`.

---

## 1. The endpoint

`POST http://localhost:8080/intake/sms/exotel`

Body is JSON with three fields (mirrors an Exotel inbound-SMS webhook):

| Field | Meaning |
|---|---|
| `From` | sender's phone (raw MSISDN; HMAC-pseudonymised before storage) |
| `SmsSid` | unique message id — repeat the same value and it's de-duplicated |
| `Body` | the SMS text (Roman/transliterated or native script) |

**Important — how location works over SMS:** an SMS has no rich metadata, so the
system first probes the text for a location.

- If the body **names a place it can resolve** → it ingests **immediately** and
  replies with a registration confirmation.
- If **no location** is found → it does **not** create a docket yet. It replies
  asking the citizen to text `LOC <village/town>, <district>`, and the complaint
  is registered once that reply arrives.

So for a **one-shot** demo, put a seeded place name in the `Body`.

---

## 2. One-shot complaint (names a place → registers immediately)

Transliterated Hindi naming **Nabarangpur**:

```bash
python - <<'PY'
import httpx
payload = {
    "From": "919812302001",
    "SmsSid": "sms-demo-0001",
    "Body": "Nabarangpur me gaon ka handpump kharab hai, teen din se paani nahi aa raha"
}
r = httpx.post("http://localhost:8080/intake/sms/exotel", json=payload, timeout=60)
print(r.status_code, r.json())   # -> {'status': 'success', 'request_id': N}
PY
```

Native script works too (Odia naming Nabarangpur, or Hindi naming Sitamarhi):

```bash
python - <<'PY'
import httpx
payload = {
    "From": "919812302002",
    "SmsSid": "sms-demo-0002",
    "Body": "सीतामढ़ी के वार्ड 5 में स्ट्रीट लाइट एक हफ्ते से खराब है।"
}
r = httpx.post("http://localhost:8080/intake/sms/exotel", json=payload, timeout=60)
print(r.status_code, r.json())
PY
```

A `NEED ` prefix is optional and stripped if present (`NEED Pune me ...` works the
same as `Pune me ...`).

curl alternative (JSON in a file avoids Windows encoding issues with non-ASCII):

```bash
curl -s -X POST http://localhost:8080/intake/sms/exotel -H "Content-Type: application/json" --data-binary @sms_body.json
```

---

## 3. Two-step location clarification (no place in the first SMS)

This shows the fallback flow. First SMS has **no location** → you get
`pending_clarification`:

```bash
python - <<'PY'
import httpx
r = httpx.post("http://localhost:8080/intake/sms/exotel",
    json={"From": "919812302010", "SmsSid": "sms-demo-0010",
          "Body": "Naali ka paani sadak par bah raha hai"}, timeout=60)
print(r.json())   # -> {'status': 'pending_clarification', ...}
PY
```

Now the citizen replies with the location (**same `From`**, new `SmsSid`). The
system pairs it with the pending problem text and registers the docket:

```bash
python - <<'PY'
import httpx
r = httpx.post("http://localhost:8080/intake/sms/exotel",
    json={"From": "919812302010", "SmsSid": "sms-demo-0011",
          "Body": "LOC Nabarangpur, Odisha"}, timeout=60)
print(r.json())   # -> {'status': 'success', 'request_id': N}
PY
```

---

## 4. Bonus: keyword commands

These don't create complaints — they show the SMS assistant working:

```bash
python - <<'PY'
import httpx
for body in ["HELP", "STATUS"]:
    r = httpx.post("http://localhost:8080/intake/sms/exotel",
        json={"From": "919812302001", "SmsSid": f"sms-cmd-{body}", "Body": body}, timeout=30)
    print(body, "->", r.json())
PY
```

- `HELP` → returns usage guidance.
- `STATUS` → looks up that sender's most recent request and reports its status +
  district (try it after §2 with the same `From`).

In mock-dispatch mode (no Exotel credentials) the outbound replies are logged to
the API console rather than actually sent — the ingest and dashboard behaviour is
identical.

---

## 5. Verify on the admin dashboard

1. **http://localhost:5174**, signed in as **`state.cell`**.
2. The newest complaint is at the **top** of the queue.

| Column | What it proves |
|---|---|
| **What was reported** | English `summary_en` = **translation**; the original SMS text (Roman or native) underneath as `raw_text` |
| **Place** | e.g. **"Nabarangpur, Odisha"** or **"Sitamarhi, Bihar"** = the **city/state** |
| **Arrived by** | **SMS** channel tag |

Note how a transliterated-Hindi SMS like *"Nabarangpur me handpump kharab hai"*
is shown to the officer in clean English — that's the translation layer doing its
job on a plain text message.

**Terminal cross-check:**

```bash
curl -s "http://localhost:8080/requests?channel=sms&limit=5" | python -m json.tool
```

Each item shows `summary_en` (English), `raw_text` (original), `district`,
`state`, and `channel: "sms"`.

---

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Response is `{"status":"pending_clarification"}` and **no row** | The `Body` had no resolvable place. Either include a seeded place, or send the `LOC <place>, <district>` follow-up (§3). |
| Response is `{"status":"empty_body"}` | `Body` was blank. |
| Response is `{"status":"duplicate"}` | You reused a `SmsSid`. Change it to simulate a new SMS. |
| **Place blank / "unmatched"** on a registered row | Not seeded, or the named place isn't in the seed. Seed and use Sitamarhi / Nabarangpur / Pune. |
| **No English translation** | `GEMINI_API_KEY` not loaded from `jansetu/.env`. Location resolution also depends on it, so without the key most SMS fall to `pending_clarification`. |
| Complaint not visible in the queue | Signed in as a state-scoped officer for a different state. Use `state.cell` or clear the state filter. |

---

**Privacy note:** the sender's number lives in memory only while ingesting and
sending the transactional reply; it is HMAC-pseudonymised before storage. No PII
is persisted.
