# Simulation Walkthrough — IVR (Interactive Voice Response)

> Historical reference, superseded on 23 September 2026. Use the [maintained documentation](../README.md) for current instructions. Earlier claims about uptime, passing-test counts, verified financial feeds, photo deletion and production security are not current assurances. Photographs are retained; financial inputs are demonstration data; officials sign-in is a demo gate. Deployment and live channel verification remain pending.

Simulate a **feature-phone voice call** entirely from the terminal — no
telephony provider, no SIM, no credentials — and watch the complaint land on the
**officials' admin dashboard** with:

- **Language translation** — English `summary_en` on top, the caller's original transcript underneath.
- **City / State** — the "Place" column resolves to a real district + state.
- **Audio → text** — feed a real `.mp3` recording and see Gemini transcribe it in the caller's chosen language.

The IVR flow mirrors a real call: greeting → **press a digit to choose a
language** → speak (or type) the problem after the beep → the system reads back a
spoken docket number and hangs up.

> Second of three files. Companion docs:
> [SIMULATION_WALKTHROUGH_WHATSAPP.md](SIMULATION_WALKTHROUGH_WHATSAPP.md) ·
> [SIMULATION_WALKTHROUGH_SMS.md](SIMULATION_WALKTHROUGH_SMS.md)

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

Then open **http://localhost:5174** and sign in as **`state.cell`** /
`jansetu@2026` (sees every state; a fresh complaint shows at the top of the
queue). Seeding is what makes the **city/state** resolve — use place names the
seed knows: **Sitamarhi** (Bihar), **Nabarangpur** (Odisha), **Pune**
(Maharashtra). Translation and audio→text use the `GEMINI_API_KEY` already
present in `jansetu/.env`.

### DTMF language keypad (feature-phone digit → language)

The simulated call selects a language by "pressing" a digit:

| Key | Language | Key | Language |
|---|---|---|---|
| **1** | Hindi | **7** | Kannada |
| **2** | Bengali | **8** | Malayalam |
| **3** | Tamil | **9** | Punjabi |
| **4** | Telugu | **0** | English |
| **5** | Marathi | **\*** | Odia |
| **6** | Gujarati | **#** | Assamese |

---

## There are three ways to simulate a call

- **Method A — Interactive CLI.** Quickest end-to-end; you type the problem. No audio.
- **Method B — HTTP full simulation.** One request runs the whole call; you pass the problem as text.
- **Method C — HTTP step-by-step.** The only way to feed a real **`.mp3`** for the audio→text demo.

---

## Method A — Interactive CLI (fastest)

```bash
cd "D:/AI Code for Communities/jansetu/backend" && python -m app.channels.simulator
```

It prompts you like a real IVR:

1. **Caller phone** — press Enter for the default `919876543210`, or type a number.
2. **Language digit** — e.g. `1` for Hindi, `5` for Marathi.
3. **Describe the problem** — type a sentence that names a seeded place, e.g.
   `पुणे में सड़क पर बड़ा गड्ढा है` (Pune → Maharashtra).

It prints each call step and the final **docket reference** (also read back as
spoken digits, exactly as the caller would hear). The complaint is now on the
dashboard. This path uses your typed text — for spoken `.mp3`, use Method C.

---

## Method B — HTTP full simulation (one request)

Runs greeting → language select → record → ingest in a single call. Good for
scripted demos. `language_digit` uses the keypad table above; `text_simulation`
is what the caller "said".

```bash
python - <<'PY'
import httpx
payload = {
    "action": "full_simulation",
    "caller_phone": "919812301001",
    "language_digit": "5",                                   # 5 = Marathi
    "text_simulation": "पुणे शहरात रस्त्यावर मोठा खड्डा आहे."   # names Pune
}
r = httpx.post("http://localhost:8080/ivr/simulate", json=payload, timeout=60)
data = r.json()
print("status:", data.get("status"))
for step in data.get("steps", []):
    print(" •", step.get("state"), "->", step.get("prompts") or step.get("docket_ref") or "")
PY
```

> `full_simulation` is text-driven (its audio path defaults to WAV). To send an
> actual `.mp3`, use Method C below.

---

## Method C — Step-by-step with a real `.mp3` (audio → text)

**Get a sample clip first.** Record a 5–10 second voice note saying a complaint
in the language you'll select, naming a seeded place — e.g. spoken Hindi for:

> "Sitamarhi mein teen din se paani ki supply band hai."

Save it as `.mp3` (also fine: `.ogg`, `.wav`) and note the path.

> ⚠️ Don't use `data/ivr_prompts/*.wav` — those are synthetic sine-tone
> placeholders, not speech, and won't transcribe. Use a real recording.

A call is a **session keyed by `caller_phone`**, so use the **same number** for
all three steps.

**Step 1 — Call starts (hear the language menu):**

```bash
python - <<'PY'
import httpx
r = httpx.post("http://localhost:8080/ivr/simulate",
    json={"action": "start", "caller_phone": "919812301055"}, timeout=30)
print(r.json()["state"], "->", [p["prompt_key"] for p in r.json()["prompts"]])
PY
```

**Step 2 — Press a language digit** (`1` = Hindi; match your clip's language):

```bash
python - <<'PY'
import httpx
r = httpx.post("http://localhost:8080/ivr/simulate",
    json={"action": "dtmf", "caller_phone": "919812301055", "digits": "1"}, timeout=30)
print("language:", r.json()["language"], "| next:", r.json()["state"])
PY
```

**Step 3 — Speak: upload the `.mp3` after the beep** (`audio_mime: "audio/mpeg"`
for mp3). This transcribes in the selected language, extracts + translates, saves
the docket, and reads back the docket digits:

```bash
python - <<'PY'
import base64, httpx
AUDIO_FILE = r"C:\Users\sagar\Downloads\sitamarhi_water.mp3"   # <-- your clip
b64 = base64.b64encode(open(AUDIO_FILE, "rb").read()).decode()
payload = {
    "action": "audio",
    "caller_phone": "919812301055",          # SAME number as steps 1–2
    "audio_base64": b64,
    "audio_mime": "audio/mpeg"               # use audio/ogg or audio/wav to match your file
}
r = httpx.post("http://localhost:8080/ivr/simulate", json=payload, timeout=90)
d = r.json()
print("state:", d["state"], "| docket:", d.get("docket_ref"), "| request_id:", d.get("request_id"))
print("spoken back:", d.get("digits_spoken"))
PY
```

If the call "drops" before Step 3 (you never send audio), **no row is created** —
by design.

---

## Verify on the admin dashboard

1. **http://localhost:5174**, signed in as **`state.cell`**.
2. Newest complaint is at the **top** of the queue.

| Column | What it proves |
|---|---|
| **What was reported** | English `summary_en` = **translation**; the transcribed original underneath |
| **Place** | e.g. **"Pune, Maharashtra"** or **"Sitamarhi, Bihar"** = the **city/state** |
| **Arrived by** | **IVR** channel tag |

Click the row for full location hierarchy, category, and urgency.

**Terminal cross-check:**

```bash
curl -s "http://localhost:8080/requests?channel=ivr&limit=5" | python -m json.tool
```

---

## Production path (for reference)

A real Exotel call posts the recording to
`POST /ivr/exotel/recording` with `CallSid`, `From`, `RecordingUrl`,
`RecordingDuration`, and `lang`. The webhook **acks the caller immediately** and
**downloads `RecordingUrl` over HTTP** in a background task (with its own DB
session) before transcribing and ingesting. Because it fetches a remote media
URL, it isn't meant for local-file demos — use **Method C** for that. In
mock-dispatch mode (no Exotel credentials) the confirmation SMS is simply logged.

---

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| **Place blank / "unmatched"** | Not seeded, or the spoken/typed text didn't name a known place. Seed and use Sitamarhi / Nabarangpur / Pune. |
| Audio step errors or empty transcript | Clip isn't real speech (not the prompt WAVs), wrong path, wrong `audio_mime`, or missing Gemini key. |
| Step 3 says wrong language | You skipped Step 2, or used a different `caller_phone` between steps (session mismatch). |
| No English translation | `GEMINI_API_KEY` not loaded from `jansetu/.env`. |
| Complaint not visible | Signed in as a state-scoped officer for a different state. Use `state.cell` or clear the state filter. |

---

**Privacy note:** the caller's number is HMAC-pseudonymised before any session or
row is written; nothing is persisted if the call drops before the recording step.
